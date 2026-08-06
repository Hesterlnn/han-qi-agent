# Provider adapters

Use one OpenAI-compatible request layer and keep provider differences in configuration. Do not hard-code API keys or assume a model name remains current.

## Common configuration

```json
{
  "provider": "custom",
  "base_url": "https://provider.example/v1",
  "api_key_env": "HAN_QI_API_KEY",
  "model": "provider-model-name",
  "protocol": "chat-completions",
  "supports_tools": false,
  "supports_files": false,
  "supports_knowledge_base": false
}
```

Keep `base_url`, model, and capability flags editable. Read the key from an environment variable. A hosted browser application must never expose a shared provider key to clients.

Web retrieval remains disabled unless the user explicitly enables it. Prefer a provider's server-side web-search tool when the active API and model support one; for example, DeepSeek's Responses API can use `web_search` with the existing `DEEPSEEK_API_KEY`. Otherwise the server may use an installed external search adapter. Expose only a single boolean control to the browser, keep adapter details and credentials out of the user interface, and never send any provider or search-service key to the browser.

## Provider families

- **OpenAI GPT:** use `https://api.openai.com/v1` with `OPENAI_API_KEY`. Prefer the Responses API for current reasoning and multi-turn workflows. Keep the model configurable; the included example uses the current balanced GPT-5.6 variant rather than assuming access to the ChatGPT web model.
- **DeepSeek:** official API supports OpenAI-compatible requests; base URL and active model names must be taken from current official documentation.
- **Alibaba Model Studio / Qwen:** supports OpenAI-compatible endpoints, visual application building, and knowledge-base applications. Region/workspace endpoints differ.
- **Zhipu GLM:** offers its own SDK and OpenAI SDK compatibility.
- **Volcengine Ark / Doubao:** supports OpenAI-style SDK use and Responses/tool workflows, including private-knowledge retrieval for supported configurations.
- **Other providers:** use the custom adapter when they expose compatible Chat Completions. Record any nonstandard request fields separately.

Official documentation:

- `https://developers.openai.com/api/docs/guides/latest-model`
- `https://api-docs.deepseek.com/zh-cn/`
- `https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope`
- `https://docs.bigmodel.cn/cn/guide/start/introduction`
- `https://www.volcengine.com/docs/82379/1958524?lang=zh`

## Ordinary-chat distribution

Pure chat products cannot execute `SKILL.md` or read a local directory. Provide:

1. a compact startup prompt;
2. one uploadable knowledge bundle;
3. a system prompt plus split knowledge files for custom-agent platforms;
4. a local/API chat option for users who want provider choice.

If a chat product has no persistent custom instructions, users must paste the startup prompt and attach the knowledge bundle again in each new conversation.

ChatGPT subscriptions and OpenAI API billing are separate. A ChatGPT or Codex login does not expose an API key to this local application.

## Generation settings

- Use a moderate creativity setting for 闲谈/情境 when supported.
- Use lower randomness or a reasoning-capable mode for 任事/考据.
- Do not depend on sampling parameters that reasoning models ignore.
- Preserve conversation history, active mode, world setting, and user-introduced facts.
- Do not transmit chain-of-thought fields between providers unless their API explicitly requires it for tool-call continuity.
