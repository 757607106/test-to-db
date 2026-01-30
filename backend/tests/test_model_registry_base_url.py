from app.core import model_registry as mr


def test_create_chat_model_strips_chat_completions_suffix(monkeypatch):
    class Dummy:
        def __init__(self, **params):
            self.params = params

    monkeypatch.setattr(mr, "_import_class", lambda _m, _c: Dummy)

    llm = mr.create_chat_model(
        provider="openai",
        model_name="glm-4.7",
        api_key="test",
        base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        timeout=1.0,
        max_retries=0,
    )

    assert llm.params["base_url"] == "https://open.bigmodel.cn/api/paas/v4"


def test_create_embedding_model_strips_embeddings_suffix(monkeypatch):
    class Dummy:
        def __init__(self, **params):
            self.params = params

    monkeypatch.setattr(mr, "_import_class", lambda _m, _c: Dummy)

    emb = mr.create_embedding_model(
        provider="openai",
        model_name="text-embedding-3-small",
        api_key="test",
        base_url="https://api.openai.com/v1/embeddings",
    )

    assert emb.params["base_url"] == "https://api.openai.com/v1"


def test_provider_list_includes_zhipu_defaults():
    providers = mr.get_provider_list_for_frontend()
    zhipu = next((p for p in providers if p.get("value") == "zhipu"), None)
    assert zhipu is not None
    assert zhipu.get("supportsChat") is True
    assert zhipu.get("defaultBaseUrl") == "https://open.bigmodel.cn/api/paas/v4"


def test_llm_configs_test_endpoint_uses_normalized_base_url(monkeypatch):
    from app.api.api_v1.endpoints import llm_configs as ep
    from app.schemas.llm_config import LLMConfigCreate
    from langchain_core.messages import AIMessage

    created_params = {}

    class Dummy:
        def __init__(self, **params):
            created_params.update(params)

        def invoke(self, _prompt):
            return AIMessage(content="pong")

    monkeypatch.setattr(mr, "_import_class", lambda _m, _c: Dummy)

    resp = ep.test_llm_connection(
        current_user=object(),
        config_in=LLMConfigCreate(
            provider="zhipu",
            api_key="test",
            base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
            model_name="glm-4.7",
            model_type="chat",
            is_active=True,
        ),
    )

    assert resp["success"] is True
    assert created_params["base_url"] == "https://open.bigmodel.cn/api/paas/v4"
