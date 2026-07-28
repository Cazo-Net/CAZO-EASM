from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_opensearch: Any | None = None
try:
    from opensearchpy import OpenSearch as _OpenSearch
    from opensearchpy.exceptions import ConnectionError as _OSConnectionError
    from opensearchpy.exceptions import NotFoundError as _OSNotFoundError
    from opensearchpy.helpers import bulk as _bulk
    _opensearch = True
except ImportError:
    _opensearch = None


class OpenSearchClient:
    def __init__(self) -> None:
        self._client: Any | None = None
        self._hosts = settings.OPENSEARCH_HOSTS
        self._user = settings.OPENSEARCH_USER
        self._password = settings.OPENSEARCH_PASSWORD
        self._verify = settings.OPENSEARCH_VERIFY_CERTS

    async def initialize(self) -> None:
        if self._client:
            return
        if not _opensearch:
            logger.warning("opensearch-py not installed — search features disabled")
            return
        try:
            self._client = _OpenSearch(
                hosts=[self._hosts],
                http_auth=(self._user, self._password),
                use_ssl=True,
                verify_certs=self._verify,
                ssl_assert_hostname=False,
                ssl_show_warn=False,
                timeout=30,
                max_retries=3,
                retry_on_timeout=True,
            )
            info = self._client.info()
            logger.info("OpenSearch connected: %s", info.get("version", {}).get("number", "unknown"))
        except Exception as e:
            logger.warning("OpenSearch connection failed (%s). Search features disabled: %s", self._hosts, e)
            self._client = None

    async def close(self) -> None:
        self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def _ensure(self) -> Any:
        if not self._client:
            raise RuntimeError("OpenSearch not connected")
        return self._client

    def create_index(self, name: str, body: dict) -> bool:
        try:
            client = self._ensure()
            if not client.indices.exists(index=name):
                client.indices.create(index=name, body=body)
                logger.info("Created OpenSearch index: %s", name)
            return True
        except Exception as e:
            logger.warning("Failed to create index %s: %s", name, e)
            return False

    def index_doc(self, index: str, doc_id: str, body: dict) -> bool:
        try:
            client = self._ensure()
            client.index(index=index, id=doc_id, body=body, refresh="wait_for")
            return True
        except Exception as e:
            logger.debug("OpenSearch index failed [%s/%s]: %s", index, doc_id, e)
            return False

    def bulk_index(self, index: str, docs: list[dict]) -> int:
        if not docs:
            return 0
        try:
            client = self._ensure()
            actions = [
                {"_index": index, "_id": doc.pop("_id", None), "_source": doc}
                for doc in docs
            ]
            success, _ = _bulk(client, actions, raise_on_error=False)
            return success
        except Exception as e:
            logger.debug("OpenSearch bulk index failed [%s]: %s", index, e)
            return 0

    def search(self, index: str, query: dict, size: int = 20) -> list[dict]:
        try:
            client = self._ensure()
            result = client.search(index=index, body=query, size=size)
            return [hit["_source"] for hit in result.get("hits", {}).get("hits", [])]
        except Exception as e:
            logger.debug("OpenSearch search failed [%s]: %s", index, e)
            return []

    def multi_search(self, indices: list[str], query: dict, size: int = 20) -> dict[str, list[dict]]:
        results: dict[str, list[dict]] = {}
        for index in indices:
            results[index] = self.search(index, query, size)
        return results

    def delete_index(self, name: str) -> bool:
        try:
            client = self._ensure()
            if client.indices.exists(index=name):
                client.indices.delete(index=name)
                return True
            return False
        except Exception:
            return False

    def health(self) -> dict[str, Any]:
        if not self._client:
            return {"connected": False}
        try:
            health = self._client.cluster.health()
            return {
                "connected": True,
                "cluster_name": health.get("cluster_name"),
                "status": health.get("status"),
                "node_count": health.get("number_of_nodes"),
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}


client = OpenSearchClient()
