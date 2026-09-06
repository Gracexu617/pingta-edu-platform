type TextGenerationResult = {
  text: string;
  providerName: string;
  model: string;
};

type AiProviderConfig = {
  provider: string; // doubao | deepseek | qwen | zhipu | kimi
  providerName: string;
  apiKey: string;
  model: string;
  baseUrl: string;
};

export type AiConfigStatus = {
  configured: boolean;
  providerName: string;
  model: string;
};

// 本项目不依赖 OpenAI。所有厂商均兼容 OpenAI /chat/completions 协议。
const PROVIDER_META: Record<
  string,
  { name: string; baseUrl: string; model: string; envKey: string; envBase: string; envModel: string }
> = {
  doubao: {
    name: "豆包",
    baseUrl: "https://ark.cn-beijing.volces.com/api/v3",
    model: "doubao-pro-32k",
    envKey: "DOUBAO_API_KEY",
    envBase: "DOUBAO_BASE_URL",
    envModel: "DOUBAO_MODEL",
  },
  deepseek: {
    name: "DeepSeek",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    envKey: "DEEPSEEK_API_KEY",
    envBase: "DEEPSEEK_BASE_URL",
    envModel: "DEEPSEEK_MODEL",
  },
  qwen: {
    name: "通义千问",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
    envKey: "QWEN_API_KEY",
    envBase: "QWEN_BASE_URL",
    envModel: "QWEN_MODEL",
  },
  zhipu: {
    name: "智谱GLM",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-plus",
    envKey: "ZHIPU_API_KEY",
    envBase: "ZHIPU_BASE_URL",
    envModel: "ZHIPU_MODEL",
  },
  kimi: {
    name: "Kimi",
    baseUrl: "https://api.moonshot.cn/v1",
    model: "moonshot-v1-8k",
    envKey: "KIMI_API_KEY",
    envBase: "KIMI_BASE_URL",
    envModel: "KIMI_MODEL",
  },
};

function normalizeBaseUrl(value: string) {
  return value.replace(/\/+$/, "");
}

function getProviderConfig(provider: string): AiProviderConfig | null {
  const meta = PROVIDER_META[provider];
  if (!meta) return null;
  const apiKey = process.env[meta.envKey];
  if (!apiKey) return null;
  const model = process.env[meta.envModel] || meta.model;
  const baseUrl = normalizeBaseUrl(process.env[meta.envBase] || meta.baseUrl);
  return { provider, providerName: meta.name, apiKey, model, baseUrl };
}

function getAiConfig(): AiProviderConfig | null {
  const raw = (process.env.AI_PROVIDER || "doubao").toLowerCase();
  // 支持 "doubao,deepseek" 形式：按顺序返回第一个配置了 key 的厂商
  const preferred = raw.split(",").map((s) => s.trim()).filter(Boolean);
  for (const p of preferred) {
    const cfg = getProviderConfig(p);
    if (cfg) return cfg;
  }
  // 兜底：遍历所有厂商，返回第一个配置了 key 的
  for (const p of Object.keys(PROVIDER_META)) {
    const cfg = getProviderConfig(p);
    if (cfg) return cfg;
  }
  return null;
}

export function getAiConfigStatus(): AiConfigStatus {
  const config = getAiConfig();

  if (!config) {
    return {
      configured: false,
      providerName: "未设置",
      model: "未设置",
    };
  }

  return {
    configured: true,
    providerName: config.providerName,
    model: config.model,
  };
}

function extractChatCompletionText(data: { choices?: Array<{ message?: { content?: string } }> }) {
  return data.choices?.map((choice) => choice.message?.content).filter(Boolean).join("\n") ?? "";
}

async function generateWithOpenAiCompatible(config: AiProviderConfig, prompt: string) {
  const response = await fetch(`${config.baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: config.model,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  if (!response.ok) {
    throw new Error(`${config.providerName} API failed: ${response.status}`);
  }

  const data = (await response.json()) as { choices?: Array<{ message?: { content?: string } }> };
  return extractChatCompletionText(data);
}

export async function generateAiText(prompt: string): Promise<TextGenerationResult | null> {
  const config = getAiConfig();
  if (!config) return null;

  const text = await generateWithOpenAiCompatible(config, prompt);
  return {
    text,
    providerName: config.providerName,
    model: config.model,
  };
}
