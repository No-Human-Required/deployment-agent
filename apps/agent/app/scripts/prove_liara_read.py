"""CLI: prove Liara read access and mark list_get_projects tested.

Usage (from apps/agent):

  # Token from Settings DB (after saving via UI/API), or:
  LIARA_API_TOKEN=... uv run python -m app.scripts.prove_liara_read

Never prints the token. Requires SECRETS_MASTER_KEY if reading token from Settings.
Requires registry seeded and DATABASE_URL reachable.
"""

from __future__ import annotations

import json
import sys

from app.config import get_settings
from app.db.session import session_scope
from app.services.liara_client import LiaraClientError
from app.services.prove_liara import prove_and_mark_tested
from app.services.registry import CapabilityNotFound, CapabilityRegistry


def main() -> int:
    settings = get_settings()
    if not settings.liara_api_token:
        # May still work if Settings UI stored a token.
        print(
            "note: LIARA_API_TOKEN unset — will try workspace Settings secret",
            file=sys.stderr,
        )
    try:
        with session_scope(settings) as session:
            # Ensure catalog row exists so promotion can succeed.
            CapabilityRegistry(session).seed()
            outcome = prove_and_mark_tested(session, settings=settings)
    except LookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except CapabilityNotFound as exc:
        print(f"error: registry missing {exc}", file=sys.stderr)
        return 3
    except LiaraClientError as exc:
        print(f"error: {exc.code}: {exc.message}", file=sys.stderr)
        return 4

    # Safe summary only — no token, no Authorization headers.
    print(json.dumps(outcome.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
