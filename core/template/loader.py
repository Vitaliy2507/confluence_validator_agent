"""Load the template rule set, transparently caching it on disk.

Resolution order:
    1. Fresh JSON cache on disk (within ``cache_ttl``) -> use it.
    2. Otherwise, fetch and parse the live Confluence template page.
    3. If that fails (network error, or no rules could be parsed), fall
       back to whatever is on disk even if stale, so the agent keeps
       working during a Confluence outage.
    4. If nothing is available at all, raise :class:`TemplateLoadError`.
"""

from __future__ import annotations

from clients.confluence_client import ConfluenceClient
from core.template.parser import parse_template_sections
from exceptions.api_errors import ConfluenceAPIError
from exceptions.validation_errors import TemplateLoadError
from models.section import TemplateRule
from parsers.html_parser import parse_sections
from utils.cache import JSONCache
from utils.logger import get_logger

logger = get_logger(__name__)


class TemplateLoader:
    """Loads and caches the :class:`TemplateRule` list used for validation."""

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        template_page_id: str,
        cache_file: str,
        cache_ttl: int,
    ) -> None:
        """Initialize the loader.

        Args:
            confluence_client: Client used to fetch the live template page.
            template_page_id: Confluence content id of the template page.
            cache_file: Path to the JSON cache file.
            cache_ttl: Freshness window for the cache, in seconds.
        """
        self._client = confluence_client
        self._page_id = template_page_id
        self._cache = JSONCache(cache_file, cache_ttl)

    def load(self, force_refresh: bool = False) -> list[TemplateRule]:
        """Return the current template rule set, refreshing the cache if stale.

        Args:
            force_refresh: If True, skip the freshness check and always
                re-fetch and re-parse the live template page, even if a
                fresh cache entry exists. Still falls back to the stale
                cache if the live fetch fails.

        Returns:
            List of :class:`TemplateRule` describing the mandatory/optional
            document structure.

        Raises:
            TemplateLoadError: If no cached rules exist and the live
                template page cannot be fetched or parsed.
        """
        rules, _source = self.load_with_source(force_refresh=force_refresh)
        return rules

    def load_with_source(
        self, force_refresh: bool = False
    ) -> tuple[list[TemplateRule], str]:
        """Same as :meth:`load`, but also reports where the rules came from.

        Args:
            force_refresh: If True, skip the freshness check and always
                re-fetch and re-parse the live template page.

        Returns:
            A ``(rules, source)`` tuple. ``source`` is one of:
            ``"cache_fresh"`` (used the on-disk cache, still within TTL),
            ``"live"`` (freshly fetched and parsed from Confluence just
            now), or ``"stale_cache_fallback"`` (the live fetch/parse
            failed or found nothing, so an old cache entry was reused).

        Raises:
            TemplateLoadError: If no cached rules exist and the live
                template page cannot be fetched or parsed.
        """
        if not force_refresh and self._cache.is_fresh():
            cached = self._cache.load()
            if cached:
                logger.info("Using cached template rules (fresh).")
                return [TemplateRule.from_dict(r) for r in cached], "cache_fresh"

        try:
            rules = self._fetch_and_parse()
            if rules:
                self._cache.save([r.to_dict() for r in rules])
                logger.info("Refreshed template rules from Confluence (%d rules).", len(rules))
                return rules, "live"
            logger.warning("Live template page yielded no rules; falling back to cache.")
        except ConfluenceAPIError as exc:
            logger.warning("Could not refresh template from Confluence: %s", exc)

        stale = self._cache.load()
        if stale:
            logger.info("Using stale cached template rules as fallback.")
            return [TemplateRule.from_dict(r) for r in stale], "stale_cache_fallback"

        raise TemplateLoadError(
            "No template rules available: Confluence fetch failed and no cache exists."
        )

    def _fetch_and_parse(self) -> list[TemplateRule]:
        page = self._client.get_page(self._page_id)
        sections = parse_sections(page.raw_html)
        return parse_template_sections(sections)
