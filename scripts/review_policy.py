"""Shared strict/local authority rules; state is not proof of chat delivery."""

from datetime import datetime

LOCAL_REVIEW_MODE = "agent-QA-user-authorized-continuous-local"
# Existing isolation records use this older explicit local-authority declaration.
LOCAL_REVIEW_MODES = {LOCAL_REVIEW_MODE, "user-authorized-continuous-local"}
AFFIRMATIVE_REPLIES = {"同意", "可以", "好的", "ok", "确认", "批准", "是", "yes", "通过"}
RECOMMENDATION_SHORTCUTS = {"按推荐", "全部按推荐", "推荐"}
CONTINUATION_REPLIES = {"继续", "继续执行", "下一步", "continue", "go on"}


def local_authorized(state: object) -> bool:
    policy = state.get("local_review_policy") if isinstance(state, dict) else None
    return isinstance(policy, dict) and policy.get("mode") == "continuous-local" and policy.get("authorized_by") == "user"


def explicit_reply_error(phrase: object, state: object) -> str | None:
    if not isinstance(phrase, str) or not phrase.strip():
        return "approval_phrase must be a non-empty string"
    normalized = phrase.strip().lower()
    if normalized in CONTINUATION_REPLIES:
        return "a continuation request is not approval of the current review packet"
    if normalized in RECOMMENDATION_SHORTCUTS or normalized in {"同意", "可以", "好的", "ok"}:
        return "explicit approval cannot use a recommendation shortcut"
    return None


def local_reply_error(phrase: object, state: object) -> str | None:
    if not local_authorized(state):
        return "local-affirmative approval requires user-authorized local production"
    if not isinstance(phrase, str) or phrase.strip().lower().rstrip("。.!！") not in AFFIRMATIVE_REPLIES:
        return "local-affirmative requires a clear affirmative to this packet; continuation, correction, and ambiguous replies do not approve it"
    return None


def review_actor_error(state: object, review: dict, *, human_only: bool = False) -> str | None:
    # Missing mode preserves the existing human declaration in historic records.
    mode = review.get("review_mode", "human")
    actor = review.get("actor", "human" if mode == "human" else "agent")
    if mode == "human" and actor == "human":
        return None
    if not human_only and isinstance(mode, str) and mode in LOCAL_REVIEW_MODES and actor == "agent" and local_authorized(state):
        try:
            if datetime.fromisoformat(review.get("reviewed_at", "")).utcoffset() is None:
                raise ValueError("timezone missing")
        except (TypeError, ValueError):
            return "local agent QA reviewed_at must be timezone-aware ISO-8601"
        return None
    return "review must declare human authority or user-authorized local agent QA"


def local_agent_review(state: object, review: object, *, status: str) -> bool:
    return local_authorized(state) and isinstance(review, dict) and review.get("status") == status and review.get("review_mode") == LOCAL_REVIEW_MODE
