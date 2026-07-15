from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class BaseScanner(ABC):
    """Abstract base class for all scanner modules."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.timeout = self.config.get("timeout", 300)
    
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
        retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute scan with exponential backoff retry."""
        last_error = None
        
        for attempt in range(retries):
            try:
                logger.info(f"Scan attempt {attempt + 1}/{retries} for {target}")
                return await asyncio.wait_for(
                    self.scan(target, **kwargs),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                last_error = f"Scan timed out after {self.timeout}s"
                logger.warning(last_error)
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Scan failed: {last_error}")
            
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        raise Exception(f"Scan failed after {retries} attempts: {last_error}")
    
    def _format_error(self, error: Exception) -> Dict[str, Any]:
        """Format error response."""
        return {
            "success": False,
            "error": str(error),
            "scanner": self.__class__.__name__
        }
