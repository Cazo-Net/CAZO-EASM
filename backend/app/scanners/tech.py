from typing import Any, Dict
from app.scanners.base import BaseScanner
import logging

logger = logging.getLogger(__name__)


class TechScanner(BaseScanner):
    """Scanner for technology detection using Wappalyzer."""
    
    def validate_target(self, target: str) -> bool:
        """Validate URL or hostname."""
        import re
        url_regex = re.compile(
            r'^(?:https?://)?'
            r'(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})'
            r'(?::\d{1,5})?'
            r'(?:/[^\s]*)?$'
        )
        return bool(url_regex.match(target))
    
    async def scan(self, target: str, **kwargs) -> Dict[str, Any]:
        """Detect technologies on target."""
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid target: {target}"))
        
        try:
            # Add protocol if missing
            url = target
            if not url.startswith(('http://', 'https://')):
                url = f"https://{url}"
            
            # Try to import Wappalyzer
            try:
                from Wappalyzer import Wappalyzer, WebPage
                
                # Initialize Wappalyzer
                wappalyzer = Wappalyzer.latest()
                
                # Analyze URL
                webpage = WebPage.new_from_url(url)
                technologies = wappalyzer.analyze_with_versions_and_categories(webpage)
                
                # Format results
                tech_list = []
                for tech_name, tech_data in technologies.items():
                    tech_list.append({
                        "name": tech_name,
                        "category": self._categorize_technology(tech_data.get('categories', [])),
                        "version": tech_data.get('versions', [None])[0] if tech_data.get('versions') else None,
                        "confidence": 100,
                        "categories": tech_data.get('categories', []),
                    })
                
                return {
                    "success": True,
                    "target": target,
                    "url": url,
                    "technologies": tech_list,
                    "count": len(tech_list),
                    "scanner": "wappalyzer"
                }
                
            except ImportError:
                # Fallback to basic detection
                return await self._basic_detection(url)
            
        except Exception as e:
            return self._format_error(e)
    
    async def _basic_detection(self, url: str) -> Dict[str, Any]:
        """Basic technology detection without Wappalyzer."""
        import httpx
        
        try:
            async with httpx.AsyncClient(verify=True, timeout=10) as client:
                response = await client.get(url)
                
                technologies = []
                headers = dict(response.headers)
                content = response.text
                
                # Check for common technologies
                checks = [
                    ("WordPress", "X-Pingback" in headers or "wp-content" in content, "CMS"),
                    ("Drupal", "X-Generator" in headers and "Drupal" in headers.get("X-Generator", ""), "CMS"),
                    ("Joomla", "Joomla" in content or "com_content" in content, "CMS"),
                    ("Nginx", "nginx" in headers.get("Server", ""), "Web Server"),
                    ("Apache", "Apache" in headers.get("Server", ""), "Web Server"),
                    ("IIS", "IIS" in headers.get("Server", ""), "Web Server"),
                    ("Cloudflare", "cf-ray" in headers, "CDN"),
                    ("React", "react" in content.lower() or "_reactRoot" in content, "JavaScript Framework"),
                    ("Vue.js", "vue" in content.lower() or "Vue" in content, "JavaScript Framework"),
                    ("Angular", "ng-version" in content or "angular" in content.lower(), "JavaScript Framework"),
                    ("jQuery", "jquery" in content.lower(), "JavaScript Library"),
                    ("Bootstrap", "bootstrap" in content.lower(), "CSS Framework"),
                    ("Google Analytics", "google-analytics.com" in content or "gtag" in content, "Analytics"),
                    ("Google Tag Manager", "googletagmanager.com" in content, "Tag Manager"),
                    ("Facebook Pixel", "fbq(" in content or "facebook.net" in content, "Analytics"),
                ]
                
                for name, detected, category in checks:
                    if detected:
                        technologies.append({
                            "name": name,
                            "category": category,
                            "version": None,
                            "confidence": 80,
                            "categories": [category],
                        })
                
                # Extract meta generator
                import re
                generator_match = re.search(r'<meta[^>]*name=["\']generator["\'][^>]*content=["\']([^"\']*)["\']', content)
                if generator_match:
                    technologies.append({
                        "name": generator_match.group(1),
                        "category": "Generator",
                        "version": None,
                        "confidence": 90,
                        "categories": ["Generator"],
                    })
                
                return {
                    "success": True,
                    "target": url,
                    "url": url,
                    "technologies": technologies,
                    "count": len(technologies),
                    "scanner": "basic_detection",
                    "note": "Basic detection used (Wappalyzer not available)"
                }
                
        except Exception as e:
            return {
                "success": True,
                "target": url,
                "url": url,
                "technologies": [],
                "count": 0,
                "error": f"Detection failed: {str(e)}",
                "scanner": "basic_detection"
            }
    
    def _categorize_technology(self, categories: list) -> str:
        """Map Wappalyzer categories to simplified category."""
        category_map = {
            "CMS": ["CMS", "Content Management System"],
            "Web Server": ["Web Server", "Server"],
            "JavaScript Framework": ["JavaScript Framework", "Frontend Framework"],
            "JavaScript Library": ["JavaScript Library", "Library"],
            "Analytics": ["Analytics", "Tracker"],
            "CDN": ["CDN", "Content Delivery Network"],
            "Programming Language": ["Programming Language"],
            "Database": ["Database"],
        }
        
        for simple_cat, wappalyzer_cats in category_map.items():
            if any(cat in wappalyzer_cats for cat in categories):
                return simple_cat
        
        return "Other"
