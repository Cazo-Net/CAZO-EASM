from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class BaseScanner(ABC):
    """Abstract base class for all scanner modules."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.timeout = self.config.get("timeout", 30)
    
    @abstractmethod
    async def scan(self, target: str, **kwargs) -> Dict[str, Any]:
        """Execute scan and return results."""
        pass
    
    @abstractmethod
    def validate_target(self, target: str) -> bool:
        """Validate target before scanning."""
        pass
    
    async def run_with_retry(
        self, 
        target: str, 
        retries: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute scan with linear backoff retry."""
        last_error = None
        
        for attempt in range(retries):
            try:
                return await asyncio.wait_for(
                    self.scan(target, **kwargs),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                last_error = f"TimeoutError: scan timed out after {self.timeout}s"
                logger.warning("%s timed out after %ss (attempt %d/%d) on %s",
                               self.__class__.__name__, self.timeout, attempt + 1, retries, target)
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                logger.warning("%s failed (attempt %d/%d) on %s: %s",
                               self.__class__.__name__, attempt + 1, retries, target, last_error)
            
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
        
        raise Exception(f"Scan failed after {retries} attempts: {last_error}")
    
    def _format_error(self, error: Exception) -> Dict[str, Any]:
        """Format error response."""
        return {
            "success": False,
            "error": str(error),
            "scanner": self.__class__.__name__
        }
