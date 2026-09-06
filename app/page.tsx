"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  createBackendMaterial,
  collectBackendPublicSocialVideos,
  createBackendSource,
  createBackendTask,
  createBackendChangzhouNews,
  createBackendSocialCreator,
  createBackendSocialVideo,
  executeBackendTask,
  generateBackendSocialVideoTranscript,
  generateBackendSocialVideoManuscript,
  getBackendPlatformAuthStatus,
  getStoredAccessPassword,
  listBackendSocialCreators,
  listBackendSocialVideoCollectionLogs,
  listBackendChangzhouNews,
  collectBackendChangzhouNews,
  listBackendSocialVideos,
  listBackendMaterials,
  listBackendSources,
  listBackendTasks,
  getHotThresholds,
  putHotThresholds,
  searchWechatArticles,
  transformWechatArticle,
  localPlatformApi,
  processBackendMaterial,
  searchBackendMaterials,
  setStoredAccessPassword,
  updateBackendMaterial,
  updateBackendSource,
  updateBackendSocialCreator,
  updateBackendTask,
} from "./lib/platform-api";
import {
  buildWorkspaceBackup,
  parseWorkspaceBackup,
  seedDrafts,
  seedMaterials,
  seedSources,
  seedSocialVideos,
  seedTasks,
  sourceTypes,
  type CollectTask,
  type Draft,
  type DraftType,
  type ChangzhouNews,
  type ImportedArticle,
  type Material,
  type SourceRecord,
  type SourceType,
  type SocialCreator,
  type SocialHotVideo,
  type SocialVideoCollectionLog,
} from "./lib/workspace";
import type {
  PlatformAuthProvider,
  WechatSearchItem,
  WechatTransformResponse,
  HotThreshold,
} from "./lib/platform-api";
import { downloadWechatExport } from "./lib/platform-api";

type ModuleKey =
  | "dashboard"
  | "sources"
  | "library"
  | "search"
  | "changzhou"
  | "hotVideos"
  | "reports"
  | "wechat"
  | "settings";

const modules: Array<{ key: ModuleKey; label: string; note: string }> = [
  { key: "dashboard", label: "总览监控", note: "运行状态" },
  { key: "sources", label: "来源管理", note: "公众号/网站/RSS" },
  { key: "library", label: "内容库", note: "资料入库处理" },
  { key: "search", label: "知识检索", note: "RAG/语义搜索" },
  { key: "changzhou", label: "常州情报", note: "升学规划预警" },
  { key: "hotVideos", label: "热门视频", note: "爆款推送阈值" },
  { key: "reports", label: "报告中心", note: "周报/月报" },
  { key: "wechat", label: "公众号转化", note: "竞品→原创" },
  { key: "settings", label: "系统配置", note: "模型/备份" },
];

const draftTypes: DraftType[] = ["公众号文章", "视频号脚本", "专业文章"];

const CHANGZHOU_GAOKAO_KEYWORDS = [
  "高考", "高三", "志愿", "志愿填报", "本科", "专科", "大学", "高校", "院校",
  "专业", "招生", "录取", "分数线", "投档", "位次", "一分一段", "强基", "综评",
  "综合评价", "选科", "合格考", "等级考", "一模", "二模", "三模", "提前批",
  "保送", "艺考", "体育单招", "中外合作", "招生简章", "本科招生", "高校招生",
  "大学招生", "招生章程", "招生计划", "院校专业组", "选科要求", "国际本科",
  "港澳高校", "内地招生", "专项计划", "高校专项", "地方专项", "国家专项",
  "少年班", "拔尖计划", "双一流", "985", "211",
];

const CHANGZHOU_NEWS_NOISE_KEYWORDS = [
  "食堂", "供餐", "安保", "反恐", "消防", "安全演练", "培训会", "工作培训",
  "党建", "工会", "慰问", "采购", "招标", "幼儿园", "幼升小", "小升初",
  "中考", "中招", "职教高考", "中职", "职高", "考研", "留学",
];

function changzhouGaokaoScore(item: ChangzhouNews) {
  const text = `${item.title} ${item.summary} ${item.category}`;
  let score = 0;
  for (const keyword of CHANGZHOU_GAOKAO_KEYWORDS) {
    if (text.includes(keyword)) score += 12;
  }
  for (const keyword of CHANGZHOU_NEWS_NOISE_KEYWORDS) {
    if (text.includes(keyword)) score -= 18;
  }
  if (item.category === "高考" || item.category === "升学规划" || item.category === "招生录取") score += 16;
  if (item.importance === "重大") score += 4;
  return score;
}

function isChangzhouGaokaoFocused(item: ChangzhouNews) {
  return changzhouGaokaoScore(item) >= 12;
}

function buildChangzhouNewsPrompt(item: ChangzhouNews) {
  const cleanSummary = item.summary.replace(/\s+/g, " ").trim();
  const sentences = cleanSummary
    .split(/(?<=[。！？!?；;])\s*/)
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 2);
  const prompt = sentences.length
    ? sentences.join("")
    : `这是一条来自${item.sourceName}的${item.category}资讯，重点关注${item.title}。`;
  return prompt.length > 110 ? `${prompt.slice(0, 108)}...` : prompt;
}

export default function Home() {
  const [activeModule, setActiveModule] = useState<ModuleKey>("dashboard");
  const [moreOpen, setMoreOpen] = useState(false);
  const [sources, setSources] = useState(seedSources);
  const [tasks, setTasks] = useState(seedTasks);
  const [materials, setMaterials] = useState(seedMaterials);
  const [drafts, setDrafts] = useState(seedDrafts);
  const [notice, setNotice] = useState("本地规则模式");
  const [aiStatus, setAiStatus] = useState("检测中");
  const [sourceBackendStatus, setSourceBackendStatus] = useState("来源后端检测中");
  const [materialBackendStatus, setMaterialBackendStatus] = useState("内容库后端检测中");
  const [taskBackendStatus, setTaskBackendStatus] = useState("任务后端检测中");
  const [changzhouBackendStatus, setChangzhouBackendStatus] = useState("常州资讯后端检测中");
  const [socialVideoBackendStatus, setSocialVideoBackendStatus] = useState("热门视频后端检测中");
  const [accessPasswordInput, setAccessPasswordInput] = useState("");
  const [accessRequired, setAccessRequired] = useState(false);
  const [platformAuthStatus, setPlatformAuthStatus] = useState<PlatformAuthProvider[]>([]);
  const [changzhouNews, setChangzhouNews] = useState<ChangzhouNews[]>([]);
  const [changzhouCategory, setChangzhouCategory] = useState<string>("全部");
  const [changzhouSort, setChangzhouSort] = useState<"published" | "created" | "importance" | "relevance">("relevance");
  const [newNewsIds, setNewNewsIds] = useState<Set<number>>(new Set());
  const [selectedChangzhouNews, setSelectedChangzhouNews] = useState<ChangzhouNews | null>(null);
  const [hotVideos, setHotVideos] = useState<SocialHotVideo[]>([]);
  const [newVideoIds, setNewVideoIds] = useState<Set<number>>(new Set());
  const [hotVideoFilter, setHotVideoFilter] = useState<"all" | "douyinPush">("douyinPush");
  const prevVideoIdsRef = useRef<Set<number>>(new Set());
  const prevNewsIdsRef = useRef<Set<number>>(new Set());
  const [socialVideoLogs, setSocialVideoLogs] = useState<SocialVideoCollectionLog[]>([]);
  const [socialCreators, setSocialCreators] = useState<SocialCreator[]>([]);
  const [creatorKeywordDrafts, setCreatorKeywordDrafts] = useState<Record<number, string>>({});
  const [selectedHotVideo, setSelectedHotVideo] = useState<SocialHotVideo | null>(null);
  const [transcribingVideoId, setTranscribingVideoId] = useState<number | null>(null);
  const [hotThresholds, setHotThresholds] = useState<HotThreshold[]>([]);
  const [thresholdDrafts, setThresholdDrafts] = useState<
    Record<string, { likes: string; saves: string }>
  >({});
  const [savingThresholds, setSavingThresholds] = useState(false);
  const [thresholdLoadError, setThresholdLoadError] = useState(false);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Material[]>([]);
  const [searchStatus, setSearchStatus] = useState("输入关键词后检索内容库");
  const [importUrl, setImportUrl] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [organizingId, setOrganizingId] = useState<number | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [wechatAccount, setWechatAccount] = useState("");
  const [wechatSearchResults, setWechatSearchResults] = useState<WechatSearchItem[]>([]);
  const [wechatSearching, setWechatSearching] = useState(false);
  const [wechatSearchError, setWechatSearchError] = useState("");
  const [wechatTransforming, setWechatTransforming] = useState(false);
  const [wechatResult, setWechatResult] = useState<WechatTransformResponse | null>(null);
  const [wechatTransformError, setWechatTransformError] = useState("");
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);
  const [executingTaskId, setExecutingTaskId] = useState<number | null>(null);
  const [backupText, setBackupText] = useState("");
  const [sourceForm, setSourceForm] = useState({
    name: "",
    type: "公众号" as SourceType,
    url: "",
    note: "",
  });
  const [materialForm, setMaterialForm] = useState({
    title: "",
    source: "公众号" as SourceType,
    tags: "",
    content: "",
  });
  const [draftTopic, setDraftTopic] = useState("");
  const [newsForm, setNewsForm] = useState({
    title: "",
    category: "政策文件",
    sourceName: "手动录入",
    url: "",
    summary: "",
  });
  const [hotVideoForm, setHotVideoForm] = useState({
    title: "",
    creator: "",
    platform: "抖音" as SocialHotVideo["platform"],
    scope: "全国大博主" as SocialHotVideo["scope"],
    url: "",
    likes: "0",
    saves: "0",
  });
  const [creatorForm, setCreatorForm] = useState({
    name: "",
    platform: "抖音" as SocialCreator["platform"],
    scope: "全国大博主" as SocialCreator["scope"],
    category: "高考升学" as SocialCreator["category"],
    profileUrl: "",
    keywords: "高考，升学，志愿填报",
  });

  function requireAccessIfNeeded(error: unknown) {
    const message = error instanceof Error ? error.message : "";
    if (message.includes("访问密码") || message.includes("401")) {
      setAccessRequired(true);
      setNotice("请输入访问密码");
    }
  }

  function submitAccessPassword() {
    setStoredAccessPassword(accessPasswordInput);
    setAccessRequired(false);
    window.location.reload();
  }

  useEffect(() => {
    setAccessPasswordInput(getStoredAccessPassword());
    const workspace = localPlatformApi.loadWorkspace();
    setSources(workspace.sources);
    setTasks(workspace.tasks);
    setMaterials(workspace.materials);
    setDrafts(workspace.drafts);
    listBackendSources()
      .then((items) => {
        setSources(items);
        setSourceBackendStatus("来源后端已连接");
        setNotice("来源已从后端数据库同步");
      })
      .catch((error) => {
        requireAccessIfNeeded(error);
        setSourceBackendStatus("来源后端不可用，使用本地缓存");
      });
    listBackendMaterials()
      .then((items) => {
        setMaterials(items);
        setMaterialBackendStatus("内容库后端已连接");
      })
      .catch((error) => {
        requireAccessIfNeeded(error);
        setMaterialBackendStatus("内容库后端不可用，使用本地缓存");
      });
    listBackendTasks()
      .then((items) => {
        setTasks(items);
        setTaskBackendStatus("任务后端已连接");
      })
      .catch((error) => {
        requireAccessIfNeeded(error);
        setTaskBackendStatus("任务后端不可用，使用本地缓存");
      });
    listBackendChangzhouNews()
      .then((items) => {
        setChangzhouNews(items);
        prevNewsIdsRef.current = new Set(items.map((item) => item.id));
        setChangzhouBackendStatus("常州资讯后端已连接");
      })
      .catch((error) => {
        requireAccessIfNeeded(error);
        setChangzhouBackendStatus("常州资讯后端不可用");
      });
    loadHotVideos();
    listBackendSocialVideoCollectionLogs()
      .then(setSocialVideoLogs)
      .catch((error) => {
        requireAccessIfNeeded(error);
        setSocialVideoLogs([]);
      });
    getBackendPlatformAuthStatus()
      .then(setPlatformAuthStatus)
      .catch((error) => {
        requireAccessIfNeeded(error);
        setPlatformAuthStatus([]);
      });
    listBackendSocialCreators()
      .then(setSocialCreators)
      .catch((error) => {
        requireAccessIfNeeded(error);
        setSocialCreators([]);
      });
    loadHotThresholds();
  }, []);

  useEffect(() => {
    // 热门视频板块每 10 分钟自动采集 + 刷新一次，发现新视频时推送通知。
    const timer = setInterval(() => {
      collectPublicHotVideos(true);
    }, 10 * 60 * 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    // 常州本地教育资讯每 5 分钟自动采集一次，发现新资讯时弹出推送横幅。
    const timer = setInterval(() => {
      collectChangzhouNews(true);
    }, 5 * 60 * 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    localPlatformApi.saveWorkspace({ sources, tasks, materials, drafts });
  }, [sources, tasks, materials, drafts]);

  useEffect(() => {
    fetch("/api/settings")
      .then((response) => response.json())
      .then((data: { aiConfigured?: boolean; model?: string }) => {
        setAiStatus(data.aiConfigured ? `AI 已配置：${data.model}` : "AI 未配置，使用本地规则");
      })
      .catch(() => setAiStatus("设置接口不可用"));
  }, []);

  const filteredMaterials = useMemo(() => {
    const key = query.trim().toLowerCase();
    if (!key) return materials;
    return materials.filter((item) =>
      [item.title, item.summary, item.content, item.tags.join(" ")]
        .join(" ")
        .toLowerCase()
        .includes(key),
    );
  }, [materials, query]);

  const activeTasks = tasks.filter((task) => task.status !== "已完成");
  const processedMaterials = materials.filter((item) => item.status === "已入库");
  const pendingDrafts = drafts.filter((draft) => draft.status !== "可发布");
  const isSourceBackendConnected = sourceBackendStatus.includes("已连接");
  const isMaterialBackendConnected = materialBackendStatus.includes("已连接");
  const isTaskBackendConnected = taskBackendStatus.includes("已连接");
  const isChangzhouBackendConnected = changzhouBackendStatus.includes("已连接");
  const monitoredWechatSources = sources.filter(
    (source) => source.type === "公众号" && source.status === "启用",
  );
  const importantChangzhouNews = changzhouNews.filter((item) => item.importance === "重大");
  // 常州情报：分类筛选 + 手动排序（最新发布 / 最新采集 / 重要性 / 升学规划相关性）。
  const changzhouCategoryCounts = useMemo(() => {
    const focused = changzhouNews.filter(isChangzhouGaokaoFocused);
    const counts: Record<string, number> = { 全部: focused.length };
    for (const item of focused) {
      counts[item.category] = (counts[item.category] ?? 0) + 1;
    }
    return counts;
  }, [changzhouNews]);
  const changzhouCategoryTabs = useMemo(
    () => ["全部", "高考", "招生录取", "升学规划", "考试测评", "政策文件"],
    [],
  );
  const displayChangzhouNews = useMemo(() => {
    const focused = changzhouNews.filter(isChangzhouGaokaoFocused);
    const filtered =
      changzhouCategory === "全部"
        ? focused
        : focused.filter((item) => item.category === changzhouCategory);
    const sorted = [...filtered];
    if (changzhouSort === "published") {
      sorted.sort((a, b) => {
        const ta = a.publishedAt === "日期未知" ? 0 : new Date(a.publishedAt).getTime();
        const tb = b.publishedAt === "日期未知" ? 0 : new Date(b.publishedAt).getTime();
        return tb - ta;
      });
    } else if (changzhouSort === "created") {
      sorted.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    } else if (changzhouSort === "importance") {
      const rank: Record<string, number> = { 重大: 3, 重要: 2, 普通: 1 };
      sorted.sort((a, b) => (rank[b.importance] ?? 0) - (rank[a.importance] ?? 0));
    } else {
      sorted.sort(
        (a, b) =>
          changzhouGaokaoScore(b) - changzhouGaokaoScore(a) ||
          ((a.publishedAt === "日期未知" ? 0 : new Date(a.publishedAt).getTime()) -
            (b.publishedAt === "日期未知" ? 0 : new Date(b.publishedAt).getTime())),
      );
    }
    return sorted;
  }, [changzhouNews, changzhouCategory, changzhouSort]);
  const pushedHotVideos = hotVideos;
  const localHotVideos = pushedHotVideos.filter((item) => item.scope === "常州本地");
  const douyinPushVideos = hotVideos.filter((item) => item.platform === "抖音" && item.isHot);
  const displayHotVideos = hotVideoFilter === "douyinPush" ? douyinPushVideos : hotVideos;
  const isSocialVideoBackendConnected = socialVideoBackendStatus.includes("已连接");

  async function addSource() {
    if (!sourceForm.name.trim()) return;
    const input = {
      name: sourceForm.name.trim(),
      type: sourceForm.type,
      url: sourceForm.url.trim(),
      note: sourceForm.note.trim(),
    };
    try {
      const source = await createBackendSource(input);
      setSources((current) => [source, ...current]);
      setSourceBackendStatus("来源后端已连接");
      setNotice("来源已写入后端数据库");
    } catch {
      setSources((current) => [localPlatformApi.createSource(input), ...current]);
      setSourceBackendStatus("来源后端不可用，已暂存本地");
      setNotice("来源已暂存本地");
    }
    setSourceForm({ name: "", type: "公众号", url: "", note: "" });
  }

  async function toggleSourceStatus(source: SourceRecord) {
    const status = source.status === "启用" ? "暂停" : "启用";
    try {
      const updated = await updateBackendSource(source, { status });
      setSources((current) => current.map((item) => (item.id === source.id ? updated : item)));
      setSourceBackendStatus("来源后端已连接");
      setNotice("来源状态已同步到后端");
    } catch {
      setSources((current) =>
        current.map((item) => (item.id === source.id ? { ...item, status } : item)),
      );
      setSourceBackendStatus("来源后端不可用，状态仅本地更新");
      setNotice("来源状态已本地更新");
    }
  }

  async function createTask(source: SourceRecord) {
    try {
      const task = await createBackendTask(source);
      setTasks((current) => [task, ...current]);
      setTaskBackendStatus("任务后端已连接");
      setNotice("采集任务已写入后端数据库");
    } catch {
      setTasks((current) => [localPlatformApi.createTask(source), ...current]);
      setTaskBackendStatus("任务后端不可用，任务已暂存本地");
      setNotice("采集任务已暂存本地");
    }
    setActiveModule("library");
  }

  async function updateTask(id: number, status: CollectTask["status"]) {
    const target = tasks.find((task) => task.id === id);
    if (!target) return;
    try {
      const updated = await updateBackendTask(target, { status });
      setTasks((current) => current.map((task) => (task.id === id ? updated : task)));
      setTaskBackendStatus("任务后端已连接");
    } catch {
      setTasks((current) =>
        current.map((task) =>
          task.id === id ? localPlatformApi.updateTask(task, { status }) : task,
        ),
      );
      setTaskBackendStatus("任务后端不可用，状态仅本地更新");
    }
  }

  async function executeTask(task: CollectTask) {
    if (executingTaskId) return;
    setExecutingTaskId(task.id);
    setNotice("正在执行采集任务");
    try {
      const result = await executeBackendTask(task);
      setTasks((current) =>
        current.map((item) => (item.id === task.id ? result.task : item)),
      );
      setMaterials((current) => [result.material, ...current]);
      setTaskBackendStatus("任务后端已连接");
      setMaterialBackendStatus("内容库后端已连接");
      setNotice("采集完成，资料已写入内容库");
    } catch {
      setNotice("采集执行失败，请确认链接可公开访问");
    } finally {
      setExecutingTaskId(null);
    }
  }

  function prepareTask(task: CollectTask) {
    setImportUrl(task.url);
    setActiveTaskId(task.id);
    updateTask(task.id, "处理中");
    setActiveModule("library");
    setNotice("任务链接已填入导入框");
  }

  async function importUrlContent() {
    const url = importUrl.trim();
    if (!url || isImporting) return;
    setIsImporting(true);
    setNotice("正在读取链接");
    try {
      const response = await fetch("/api/import-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const result = (await response.json()) as ImportedArticle & { error?: string };
      if (!response.ok || result.error) {
        setNotice(result.error ?? "链接导入失败，请手动粘贴正文");
        return;
      }
      const task = activeTaskId ? tasks.find((item) => item.id === activeTaskId) : null;
      setMaterialForm({
        title: result.title,
        source: task?.sourceType ?? result.source,
        tags: task?.sourceName ? [...result.tags, task.sourceName].join("，") : result.tags.join("，"),
        content: result.content,
      });
      setImportUrl("");
      setNotice(task ? "任务内容已读取，请确认入库" : "链接已读取，请确认入库");
    } catch {
      setNotice("链接导入接口不可用");
    } finally {
      setIsImporting(false);
    }
  }

  async function addMaterial() {
    if (!materialForm.title.trim() || !materialForm.content.trim()) return;
    const task = activeTaskId ? tasks.find((item) => item.id === activeTaskId) : null;
    const tags = materialForm.tags
      .split(/[，,]/)
      .map((tag) => tag.trim())
      .filter(Boolean);
    const input = {
      title: materialForm.title.trim(),
      source: materialForm.source,
      sourceName: task?.sourceName,
      taskId: task?.id,
      tags: tags.length ? tags : ["待标注"],
      summary:
        materialForm.content.length > 72
          ? `${materialForm.content.slice(0, 72)}...`
          : materialForm.content,
      content: materialForm.content.trim(),
    };
    try {
      const material = await createBackendMaterial(input);
      setMaterials((current) => [material, ...current]);
      setMaterialBackendStatus("内容库后端已连接");
      setNotice(task ? "资料已写入后端，任务已完成" : "资料已写入后端数据库");
    } catch {
      setMaterials((current) => [localPlatformApi.createDocument(input), ...current]);
      setMaterialBackendStatus("内容库后端不可用，已暂存本地");
      setNotice(task ? "资料已本地入库，任务已完成" : "资料已暂存本地");
    }
    if (task) await updateTask(task.id, "已完成");
    setActiveTaskId(null);
    setMaterialForm({ title: "", source: "公众号", tags: "", content: "" });
  }

  async function toggleMaterialStatus(item: Material) {
    const status = item.status === "已入库" ? "待整理" : "已入库";
    try {
      const updated = await updateBackendMaterial(item, { status });
      setMaterials((current) =>
        current.map((material) => (material.id === item.id ? updated : material)),
      );
      setMaterialBackendStatus("内容库后端已连接");
      setNotice("资料状态已同步到后端");
    } catch {
      setMaterials((current) =>
        current.map((material) => (material.id === item.id ? { ...material, status } : material)),
      );
      setMaterialBackendStatus("内容库后端不可用，状态仅本地更新");
      setNotice("资料状态已本地更新");
    }
  }

  async function organizeMaterial(item: Material) {
    if (organizingId) return;
    setOrganizingId(item.id);
    setNotice("正在整理资料");
    try {
      const processed = await processBackendMaterial(item);
      setMaterials((current) =>
        current.map((material) => (material.id === item.id ? processed : material)),
      );
      setMaterialBackendStatus("内容库后端已连接");
      setNotice("后端处理完成：摘要、标签、关键词已更新");
      return;
    } catch {
      setMaterialBackendStatus("内容库后端不可用，尝试本地整理");
    }
    try {
      const response = await fetch("/api/organize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ material: item }),
      });
      const result = (await response.json()) as { summary?: string; tags?: string[]; mode?: string };
      if (response.ok && result.summary && result.tags?.length) {
        const updated = { ...item, summary: result.summary, tags: result.tags, status: "已入库" as const };
        try {
          const backendUpdated = await updateBackendMaterial(item, {
            summary: updated.summary,
            tags: updated.tags,
            status: updated.status,
          });
          setMaterials((current) =>
            current.map((material) => (material.id === item.id ? backendUpdated : material)),
          );
          setMaterialBackendStatus("内容库后端已连接");
        } catch {
          setMaterials((current) =>
            current.map((material) => (material.id === item.id ? updated : material)),
          );
          setMaterialBackendStatus("内容库后端不可用，整理结果仅本地更新");
        }
        setNotice(result.mode ?? "资料已整理");
      }
    } catch {
      setNotice("整理接口不可用");
    } finally {
      setOrganizingId(null);
    }
  }

  async function generateDraft(type: DraftType) {
    if (isGenerating) return;
    const base = filteredMaterials[0] ?? materials[0];
    const topic = draftTopic.trim() || "基于资料库的新选题";
    setIsGenerating(true);
    setNotice("正在生成草稿");
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, topic, material: base }),
      });
      const result = (await response.json()) as { body?: string; mode?: string };
      setDrafts((current) => [
        {
          id: Date.now(),
          type,
          title: `${type}：${topic}`,
          basedOn: base?.title ?? "暂无资料",
          status: "待审核",
          body: result.body ?? "生成失败，请重试。",
        },
        ...current,
      ]);
      setNotice(result.mode ?? "草稿已生成");
      setDraftTopic("");
    } catch {
      setNotice("生成接口不可用");
    } finally {
      setIsGenerating(false);
    }
  }

  async function runSearch() {
    try {
      const items = await searchBackendMaterials(query);
      setSearchResults(items);
      setSearchStatus(`后端检索完成：${items.length} 条结果`);
    } catch {
      setSearchResults(filteredMaterials);
      setSearchStatus(`后端检索不可用，本地匹配：${filteredMaterials.length} 条`);
    }
  }

  async function addChangzhouNews() {
    if (!newsForm.title.trim()) return;
    try {
      const item = await createBackendChangzhouNews(newsForm);
      setChangzhouNews((current) => [item, ...current]);
      setChangzhouBackendStatus("常州资讯后端已连接");
      setNotice("常州本地教育资讯已入库");
      setNewsForm({ title: "", category: "政策", sourceName: "手动录入", url: "", summary: "" });
    } catch {
      setNotice("常州资讯入库失败");
    }
  }

  async function addHotVideo() {
    if (!hotVideoForm.title.trim() || !hotVideoForm.creator.trim() || !hotVideoForm.url.trim()) {
      setNotice("请填写标题、博主和原视频链接");
      return;
    }
    try {
      const item = await createBackendSocialVideo({
        title: hotVideoForm.title.trim(),
        creator: hotVideoForm.creator.trim(),
        platform: hotVideoForm.platform,
        scope: hotVideoForm.scope,
        url: hotVideoForm.url.trim(),
        likes: Number(hotVideoForm.likes) || 0,
        saves: Number(hotVideoForm.saves) || 0,
      });
      setHotVideos((current) => [item, ...current]);
      prevVideoIdsRef.current = new Set([...prevVideoIdsRef.current, item.id]);
      setSocialVideoBackendStatus("热门视频后端已连接");
      setNotice(item.reason);
      setHotVideoForm({
        title: "",
        creator: "",
        platform: "抖音",
        scope: "全国大博主",
        url: "",
        likes: "0",
        saves: "0",
      });
    } catch {
      setNotice("视频入库失败，请确认链接是完整 URL");
    }
  }

  function ingestVideos(items: SocialHotVideo[], announce: boolean) {
    const prev = prevVideoIdsRef.current;
    const incomingIds = new Set(items.map((item) => item.id));
    const freshIds = items.filter((item) => !prev.has(item.id)).map((item) => item.id);
    setHotVideos(items);
    prevVideoIdsRef.current = incomingIds;
    if (announce && freshIds.length > 0) {
      setNewVideoIds(new Set(freshIds));
      setNotice(`📣 本周期推送 ${freshIds.length} 条新抖音爆款，已高亮展示`);
    } else if (announce) {
      setNewVideoIds(new Set());
      setNotice("已是最新，暂无新的达标视频");
    } else {
      setNewVideoIds(new Set());
    }
  }

  async function loadHotVideos() {
    try {
      const items = await listBackendSocialVideos();
      ingestVideos(items, false);
      setSocialVideoBackendStatus("热门视频后端已连接");
    } catch {
      ingestVideos(seedSocialVideos, false);
      setSocialVideoBackendStatus("热门视频后端不可用，使用本地缓存样例");
    }
  }

  async function collectPublicHotVideos(announce = true) {
    try {
      await collectBackendPublicSocialVideos();
      const [videos, logs] = await Promise.all([
        listBackendSocialVideos(),
        listBackendSocialVideoCollectionLogs(),
      ]);
      ingestVideos(videos, announce);
      setSocialVideoLogs(logs);
      setSocialVideoBackendStatus("热门视频后端已连接");
    } catch {
      if (announce) setNotice("自动采集失败，可能需要平台授权或网络恢复");
    }
  }

  function thresholdKey(item: Pick<HotThreshold, "platform" | "scope">) {
    return `${item.platform}|${item.scope}`;
  }

  function thresholdLabel(item: Pick<HotThreshold, "platform" | "scope">) {
    return item.scope === "常州本地"
      ? `${item.scope} · ${item.platform}`
      : `全国大博主 · ${item.platform}`;
  }

  function applyThresholdDrafts(items: HotThreshold[]) {
    setHotThresholds(items);
    setThresholdDrafts(
      Object.fromEntries(
        items.map((item) => [
          thresholdKey(item),
          { likes: String(item.likes), saves: String(item.saves) },
        ]),
      ),
    );
  }

  async function loadHotThresholds() {
    try {
      const items = await getHotThresholds();
      applyThresholdDrafts(items);
      setThresholdLoadError(false);
    } catch {
      setThresholdLoadError(true);
    }
  }

  async function saveHotThresholds() {
    if (savingThresholds || !hotThresholds.length) return;
    setSavingThresholds(true);
    try {
      const payload = hotThresholds.map((item) => {
        const draft = thresholdDrafts[thresholdKey(item)];
        return {
          platform: item.platform,
          scope: item.scope,
          likes: Math.max(0, Number(draft?.likes) || 0),
          saves: Math.max(0, Number(draft?.saves) || 0),
        };
      });
      const saved = await putHotThresholds(payload);
      applyThresholdDrafts(saved);
      await loadHotVideos();
      setThresholdLoadError(false);
      setNotice("热门视频推送门槛已保存，后续采集会按新标准推送");
    } catch {
      setThresholdLoadError(true);
      setNotice("门槛保存失败，请确认后端服务可用");
    } finally {
      setSavingThresholds(false);
    }
  }

  function ingestChangzhouNews(items: ChangzhouNews[], announce: boolean) {
    const prev = prevNewsIdsRef.current;
    const incomingIds = new Set(items.map((item) => item.id));
    const freshIds = items.filter((item) => !prev.has(item.id)).map((item) => item.id);
    setChangzhouNews(items);
    prevNewsIdsRef.current = incomingIds;
    if (announce && freshIds.length > 0) {
      setNewNewsIds(new Set(freshIds));
      setNotice(`📣 本周期推送 ${freshIds.length} 条新常州教育资讯，已高亮展示`);
    } else if (announce) {
      setNewNewsIds(new Set());
      setNotice("已是最新，暂无新的常州教育资讯");
    } else {
      setNewNewsIds(new Set());
    }
  }

  async function collectChangzhouNews(announce = true) {
    try {
      await collectBackendChangzhouNews();
      const items = await listBackendChangzhouNews();
      ingestChangzhouNews(items, announce);
      setChangzhouBackendStatus("常州资讯后端已连接");
    } catch {
      if (announce) setNotice("常州资讯自动采集失败，可能需要网络恢复");
    }
  }

  async function generateHotVideoTranscript(item: SocialHotVideo) {
    setTranscribingVideoId(item.id);
    try {
      const updated = await generateBackendSocialVideoTranscript(item.id);
      setHotVideos((current) => current.map((video) => (video.id === updated.id ? updated : video)));
      setSelectedHotVideo(updated);
      setNotice("已生成语音转文字、去语气词与文稿");
    } catch {
      setNotice("视频文稿提取失败");
    } finally {
      setTranscribingVideoId(null);
    }
  }

  async function generateHotVideoManuscript(item: SocialHotVideo) {
    setTranscribingVideoId(item.id);
    try {
      const updated = await generateBackendSocialVideoManuscript(item.id);
      setHotVideos((current) => current.map((video) => (video.id === updated.id ? updated : video)));
      setSelectedHotVideo(updated);
      setNotice(updated.manuscript ? "文稿已重新生成" : "暂无可生成文稿，请先提取转写");
    } catch {
      setNotice("文稿生成失败");
    } finally {
      setTranscribingVideoId(null);
    }
  }

  async function saveManuscriptToLibrary(item: SocialHotVideo) {
    if (!item.manuscript.trim()) {
      setNotice("还没有文稿可存入内容库");
      return;
    }
    try {
      await createBackendMaterial({
        title: item.title,
        source: item.creator,
        sourceName: item.creator,
        tags: ["视频转写文稿", item.platform],
        summary: item.title,
        content: item.manuscript,
      });
      setNotice("文稿已存入内容库，可在内容库/蒸馏中继续加工");
    } catch {
      setNotice("存入内容库失败");
    }
  }

  async function addSocialCreator() {
    if (!creatorForm.name.trim()) {
      setNotice("请填写博主名称");
      return;
    }
    try {
      const item = await createBackendSocialCreator({
        name: creatorForm.name.trim(),
        platform: creatorForm.platform,
        scope: creatorForm.scope,
        category: creatorForm.category,
        profileUrl: creatorForm.profileUrl.trim(),
        keywords: creatorForm.keywords
          .split(/[，,]/)
          .map((keyword) => keyword.trim())
          .filter(Boolean),
      });
      setSocialCreators((current) => [item, ...current]);
      setNotice("高考升学博主已加入采集池");
      setCreatorForm({
        name: "",
        platform: "抖音",
        scope: "全国大博主",
        category: "高考升学",
        profileUrl: "",
        keywords: "高考，升学，志愿填报",
      });
    } catch {
      setNotice("博主加入失败，可能已存在");
    }
  }

  async function saveSocialCreator(item: SocialCreator) {
    const keywordText = creatorKeywordDrafts[item.id] ?? item.keywords.join("，");
    try {
      const updated = await updateBackendSocialCreator(item, {
        keywords: keywordText
          .split(/[，,]/)
          .map((keyword) => keyword.trim())
          .filter(Boolean),
      });
      setSocialCreators((current) =>
        current.map((creator) => (creator.id === updated.id ? updated : creator)),
      );
      setCreatorKeywordDrafts((current) => {
        const next = { ...current };
        delete next[item.id];
        return next;
      });
      setNotice("博主关键词已保存，后续采集会按新规则筛选");
    } catch {
      setNotice("博主配置保存失败");
    }
  }

  async function toggleSocialCreator(item: SocialCreator) {
    try {
      const updated = await updateBackendSocialCreator(item, { enabled: !item.enabled });
      setSocialCreators((current) =>
        current.map((creator) => (creator.id === updated.id ? updated : creator)),
      );
      setNotice(updated.enabled ? "博主已启用，自动采集会读取该账号" : "博主已暂停，自动采集会跳过该账号");
    } catch {
      setNotice("博主状态更新失败");
    }
  }

  function exportWorkspace() {
    const text = JSON.stringify(buildWorkspaceBackup({ sources, tasks, materials, drafts }), null, 2);
    const blob = new Blob([text], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `education-intel-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setNotice("工作区已导出");
  }

  function importWorkspace(file?: File) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const backup = parseWorkspaceBackup(String(reader.result ?? ""));
      if (!backup) {
        setNotice("备份格式错误");
        return;
      }
      setSources(backup.sources);
      setTasks(backup.tasks);
      setMaterials(backup.materials);
      setDrafts(backup.drafts);
      setNotice("工作区已恢复");
    };
    reader.readAsText(file, "utf-8");
  }

  function resetDemo() {
    setSources(seedSources);
    setTasks(seedTasks);
    setMaterials(seedMaterials);
    setDrafts(seedDrafts);
    setNotice("已恢复演示数据");
  }

  if (accessRequired) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-transparent px-5 text-[#16243b]">
        <section className="glass w-full max-w-md rounded-3xl p-6 shadow-sm">
          <div className="mb-5 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#164b86] font-academic text-xl font-bold text-white shadow-sm">
              凭
            </span>
            <div>
              <p className="font-academic text-lg font-bold text-[#164b86]">凭他教育</p>
              <p className="text-xs text-[#5b6b82]">请输入访问密码</p>
            </div>
          </div>
          <input
            className="field"
            type="password"
            value={accessPasswordInput}
            onChange={(event) => setAccessPasswordInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") submitAccessPassword();
            }}
            placeholder="访问密码"
          />
          <button className="primary-button mt-4 w-full" onClick={submitAccessPassword}>
            进入平台
          </button>
          <p className="mt-3 text-sm leading-6 text-[#5b6b82]">
            这个密码由平台管理员提供，用来保护采集额度和内容数据。
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-transparent text-[#16243b]">
      <div className="mx-auto flex max-w-[1500px] gap-6 px-5 py-5">
        <aside className="glass sticky top-5 hidden h-[calc(100vh-40px)] w-72 shrink-0 rounded-3xl p-5 lg:block">
          <div className="mb-7">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#164b86] font-academic text-xl font-bold text-white shadow-sm">
                凭
              </span>
              <div className="leading-tight">
                <p className="font-academic text-lg font-bold text-[#164b86]">凭他教育</p>
                <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-[#b18a4a]">
                  PINGTA EDU
                </p>
              </div>
            </div>
            <div className="mt-4 h-px w-full bg-gradient-to-r from-[#b18a4a] via-[#d8c39a] to-transparent"></div>
            <p className="mt-3 font-display text-[11px] font-semibold uppercase tracking-[0.22em] text-[#b18a4a]">
              Content Intelligence
            </p>
            <h1 className="mt-2 font-academic text-2xl font-bold tracking-tight text-[#164b86]">教育内容中台</h1>
            <p className="mt-2 text-sm leading-6 text-[#5b6b82]">AI 助理团队驱动的内容生产 · 情报 · 审核平台</p>
          </div>
          <nav className="space-y-1">
            {modules
              .filter((m) => ["dashboard", "changzhou", "hotVideos", "wechat"].includes(m.key))
              .map((item) => (
                <button
                  className={`group relative w-full overflow-hidden rounded-md border-l-2 px-3 py-2 text-left transition ${
                    activeModule === item.key
                      ? "border-[#164b86] bg-[#164b86]/12 shadow-sm"
                      : "border-transparent hover:bg-white/50"
                  }`}
                  key={item.key}
                  onClick={() => setActiveModule(item.key)}
                >
                  <span className="block text-sm font-semibold">{item.label}</span>
                  <span className="block text-xs text-[#5b6b82]">{item.note}</span>
                </button>
              ))}
            <button
              className="mt-2 flex w-full items-center justify-between rounded-md border border-transparent px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.14em] text-[#5b6b82] transition hover:bg-white/50"
              onClick={() => setMoreOpen((o) => !o)}
            >
              <span>更多模块</span>
              <span className="text-[10px]">{moreOpen ? "收起 ▲" : "展开 ▼"}</span>
            </button>
            {moreOpen &&
              modules
                .filter((m) => !["dashboard", "changzhou", "hotVideos", "wechat"].includes(m.key))
                .map((item) => (
                  <button
                    className={`group relative w-full overflow-hidden rounded-md border-l-2 px-3 py-2 pl-5 text-left text-sm transition ${
                      activeModule === item.key
                        ? "border-[#164b86] bg-[#164b86]/12 shadow-sm"
                        : "border-transparent hover:bg-white/50"
                    }`}
                    key={item.key}
                    onClick={() => setActiveModule(item.key)}
                  >
                    <span className="block font-semibold">{item.label}</span>
                    <span className="block text-xs text-[#5b6b82]">{item.note}</span>
                  </button>
                ))}
          </nav>
        </aside>

        <section className="min-w-0 flex-1 space-y-5">
          <header className="card page-header p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center">
              <div className="mr-auto">
                <p className="eyebrow mb-1">
                  {modules.find((item) => item.key === activeModule)?.note}
                </p>
                <h2 className="font-academic text-2xl font-semibold tracking-tight">
                  {modules.find((item) => item.key === activeModule)?.label}
                </h2>
                <p className="mt-1 text-xs text-[#5b6b82]">{notice}</p>
              </div>
              <div
                className={`pill px-3 py-2 text-sm font-semibold ${
                  isSourceBackendConnected
                    ? "border-[#a9c8ea] bg-[#164b86]/12 text-[#164b86]"
                    : "border-[#e8d6a8] bg-[#b18a4a]/14 text-[#8a5a0f]"
                }`}
              >
                {sourceBackendStatus}
              </div>
              <select
                className="field lg:hidden"
                onChange={(event) => setActiveModule(event.target.value as ModuleKey)}
                value={activeModule}
              >
                {modules.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.label}
                  </option>
                ))}
              </select>
              <input
                className="field md:w-80"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索资料、标签、摘要"
                value={query}
              />
            </div>
          </header>

          {activeModule === "dashboard" && (
            <section className="space-y-5">
              <div className="grid gap-3 md:grid-cols-5">
                {[
                  [isSourceBackendConnected ? "后端来源" : "本地来源", sources.length],
                  ["活跃任务", activeTasks.length],
                  ["已入库资料", processedMaterials.length],
                  ["常州资讯", changzhouNews.length],
                  ["抖音推送", douyinPushVideos.length],
                  ["待审草稿", pendingDrafts.length],
                ].map(([label, value]) => (
                  <div className="card p-4" key={label}>
                    <p className="text-sm text-[#5b6b82]">{label}</p>
                    <p className="mt-2 text-3xl font-semibold">{value}</p>
                  </div>
                ))}
              </div>
              <div className="grid gap-4 xl:grid-cols-3">
                <StatusPanel
                  title="采集运行"
                  items={[
                    sourceBackendStatus,
                    taskBackendStatus,
                    `已监控公众号：${monitoredWechatSources.map((source) => source.name).join("、") || "暂无"}`,
                  ]}
                />
                <StatusPanel title="AI 能力" items={[aiStatus, "摘要 / 标签：可用"]} />
                <StatusPanel title="内容库" items={[materialBackendStatus]} />
              </div>
              <Card title="常州本地教育实时资讯" note={changzhouBackendStatus}>
                <div
                  className={`mb-3 pill px-4 py-3 text-sm ${
                    isChangzhouBackendConnected
                      ? "border-[#a9c8ea] bg-[#164b86]/12 text-[#164b86]"
                      : "border-[#e8d6a8] bg-[#b18a4a]/14 text-[#8a5a0f]"
                  }`}
                >
                  已接入常州政策文件、校园公告、招生录取、学区划片、考试测评与校园开放日情报入口。
                  {importantChangzhouNews.length > 0 && ` 当前有 ${importantChangzhouNews.length} 条重大更新。`}
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {changzhouNews.slice(0, 4).map((item) => (
                    <ChangzhouNewsCard
                      item={item}
                      key={item.id}
                      onOpen={() => setSelectedChangzhouNews(item)}
                    />
                  ))}
                </div>
                {!changzhouNews.length && (
                  <p className="card-dashed p-4 text-sm text-[#5b6b82]">
                    正在等待常州本地教育资讯同步。
                  </p>
                )}
                <button className="secondary-button mt-3" onClick={() => setActiveModule("changzhou")}>
                  查看全部 / 手动入库
                </button>
              </Card>
              <Card title="大博主热门视频推送" note={socialVideoBackendStatus}>
                <div
                  className={`mb-3 pill px-4 py-3 text-sm ${
                    isSocialVideoBackendConnected
                      ? "border-[#a9c8ea] bg-[#164b86]/12 text-[#164b86]"
                      : "border-[#e8d6a8] bg-[#b18a4a]/14 text-[#8a5a0f]"
                  }`}
                >
                  每 10 分钟自动采集一次，凡是抖音达标的视频都会推送给你。
                </div>
                <div className="mb-3 grid gap-2 text-sm text-[#334155] md:grid-cols-2">
                  <p className="chip p-3">大博主抖音：1250赞或500收藏</p>
                  <p className="chip p-3">大博主视频号：250赞或50收藏</p>
                  <p className="chip p-3">常州抖音：125赞或50收藏</p>
                  <p className="chip p-3">常州视频号：50赞或18收藏</p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {douyinPushVideos.slice(0, 4).map((item) => (
                    <HotVideoCard
                      item={item}
                      key={item.id}
                      isNew={newVideoIds.has(item.id)}
                      onOpen={() => setSelectedHotVideo(item)}
                    />
                  ))}
                </div>
                {!douyinPushVideos.length && (
                  <p className="card-dashed p-4 text-sm text-[#5b6b82]">
                    暂无抖音推送。采集器会继续按标准寻找内容。
                  </p>
                )}
                <button className="secondary-button mt-3" onClick={() => setActiveModule("hotVideos")}>
                  查看全部热门视频
                </button>
                <button className="secondary-button mt-3 ml-2" onClick={collectPublicHotVideos}>
                  自动采集公开视频
                </button>
              </Card>
            </section>
          )}

          {activeModule === "sources" && (
            <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
              <Card title="来源列表" note="后续自动监控对象">
                <div
                  className={`mb-3 pill px-4 py-3 text-sm ${
                    isSourceBackendConnected
                      ? "border-[#a9c8ea] bg-[#164b86]/12 text-[#164b86]"
                      : "border-[#e8d6a8] bg-[#b18a4a]/14 text-[#8a5a0f]"
                  }`}
                >
                  {isSourceBackendConnected
                    ? "已连接后端 · 长期保存"
                    : "本地缓存 · 待同步"}
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {sources.map((source) => (
                    <article
                      className={`card p-4 ${
                        source.name === "龙城家长圈"
                          ? "border-[#164b86] bg-[#e7f0fc]"
                          : "border-[#d6e2f2]"
                      }`}
                      key={source.id}
                    >
                      <div className="flex gap-2">
                        <div className="mr-auto">
                          <h3 className="font-semibold">{source.name}</h3>
                          <p className="mt-1 text-sm text-[#5b6b82]">{source.note || "暂无备注"}</p>
                        </div>
                        <Badge>{source.type}</Badge>
                        <Badge>{source.status}</Badge>
                      </div>
                      {source.name === "龙城家长圈" && (
                        <p className="mt-3 rounded bg-[#164b86] px-3 py-2 text-sm font-semibold text-white">
                          已监控公众号，数据源保存在后端数据库
                        </p>
                      )}
                      {source.url && <p className="mt-3 break-all text-xs text-[#5b6b82]">{source.url}</p>}
                      <div className="mt-3 flex flex-wrap gap-2 border-t border-[#e3ebf5] pt-3">
                        <button
                          className="secondary-button"
                          onClick={() => toggleSourceStatus(source)}
                        >
                          {source.status === "启用" ? "暂停" : "启用"}
                        </button>
                        <span className="rounded-md border border-[#d6e2f2] bg-white/70 px-3 py-2 text-sm font-semibold text-[#5b6b82]">
                          {source.status === "启用" ? "自动监控中" : "已暂停"}
                        </span>
                      </div>
                    </article>
                  ))}
                </div>
              </Card>
              <Card title="新增来源" note="先配置，后接自动采集">
                <div className="space-y-3">
                  <input className="field" placeholder="来源名称" value={sourceForm.name} onChange={(e) => setSourceForm({ ...sourceForm, name: e.target.value })} />
                  <select className="field" value={sourceForm.type} onChange={(e) => setSourceForm({ ...sourceForm, type: e.target.value as SourceType })}>
                    {sourceTypes.map((type) => <option key={type}>{type}</option>)}
                  </select>
                  <input className="field" placeholder="入口链接" value={sourceForm.url} onChange={(e) => setSourceForm({ ...sourceForm, url: e.target.value })} />
                  <textarea className="field min-h-24 resize-none" placeholder="采集重点/频率/备注" value={sourceForm.note} onChange={(e) => setSourceForm({ ...sourceForm, note: e.target.value })} />
                  <button className="primary-button" onClick={addSource}>添加来源</button>
                </div>
              </Card>
            </section>
          )}

          {activeModule === "library" && (
            <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
              <Card title="内容库" note="资料、标签、摘要、任务来源">
                <div
                  className={`mb-3 pill px-4 py-3 text-sm ${
                    isMaterialBackendConnected
                      ? "border-[#a9c8ea] bg-[#164b86]/12 text-[#164b86]"
                      : "border-[#e8d6a8] bg-[#b18a4a]/14 text-[#8a5a0f]"
                  }`}
                >
                  {isMaterialBackendConnected
                    ? "已连接后端 · 长期保存"
                    : "本地缓存 · 待同步"}
                </div>
                <div className="grid gap-3">
                  {filteredMaterials.map((item) => (
                    <article className="card p-4" key={item.id}>
                      <div className="flex flex-wrap gap-2">
                        <h3 className="mr-auto font-semibold">{item.title}</h3>
                        <Badge>{item.source}</Badge>
                        <Badge>{item.status}</Badge>
                      </div>
                      {item.sourceName && <p className="mt-2 text-xs text-[#64748b]">来源：{item.sourceName}</p>}
                      <p className="mt-3 text-sm leading-6 text-[#334155]">{item.summary}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}
                      </div>
                      {item.keywords?.length ? (
                        <p className="mt-2 text-xs text-[#5b6b82]">
                          关键词：{item.keywords.join("、")}
                        </p>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2 border-t border-[#e3ebf5] pt-3">
                        <button className="secondary-button" disabled={organizingId === item.id} onClick={() => organizeMaterial(item)}>
                          {organizingId === item.id ? "整理中" : "AI整理"}
                        </button>
                        <button className="secondary-button" onClick={() => toggleMaterialStatus(item)}>
                          切换状态
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </Card>
              <Card title="导入/入库" note="链接导入失败时手动粘贴">
                <div className="space-y-3">
                  <input className="field" placeholder="文章链接" value={importUrl} onChange={(e) => setImportUrl(e.target.value)} />
                  {activeTaskId && <p className="text-xs text-[#82602a]">关联任务 #{activeTaskId}</p>}
                  <button className="secondary-button" disabled={isImporting} onClick={importUrlContent}>{isImporting ? "导入中" : "链接导入"}</button>
                  <input className="field" placeholder="标题" value={materialForm.title} onChange={(e) => setMaterialForm({ ...materialForm, title: e.target.value })} />
                  <select className="field" value={materialForm.source} onChange={(e) => setMaterialForm({ ...materialForm, source: e.target.value as SourceType })}>
                    {sourceTypes.map((type) => <option key={type}>{type}</option>)}
                  </select>
                  <input className="field" placeholder="标签，逗号分隔" value={materialForm.tags} onChange={(e) => setMaterialForm({ ...materialForm, tags: e.target.value })} />
                  <textarea className="field min-h-32 resize-none" placeholder="正文/转写文本" value={materialForm.content} onChange={(e) => setMaterialForm({ ...materialForm, content: e.target.value })} />
                  <button className="primary-button" onClick={addMaterial}>入库</button>
                </div>
              </Card>
            </section>
          )}

          {activeModule === "search" && (
            <section className="grid gap-5 xl:grid-cols-[420px_1fr]">
              <Card title="知识检索" note="全文检索内容库">
                <div className="space-y-3">
                  <input
                    className="field"
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="输入关键词，例如：中考、招生、常州"
                    value={query}
                  />
                  <button className="primary-button" onClick={runSearch}>检索内容库</button>
                  <p className="text-sm text-[#5b6b82]">{searchStatus}</p>
                </div>
              </Card>
              <Card title="检索结果" note="返回资料、摘要、标签、关键词">
                <div className="grid gap-3">
                  {(searchResults.length ? searchResults : filteredMaterials).map((item) => (
                    <article className="card p-4" key={item.id}>
                      <div className="flex flex-wrap gap-2">
                        <h3 className="mr-auto font-semibold">{item.title}</h3>
                        <Badge>{item.source}</Badge>
                        <Badge>{item.status}</Badge>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-[#334155]">{item.summary}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)}
                      </div>
                      {item.keywords?.length ? (
                        <p className="mt-2 text-xs text-[#5b6b82]">
                          关键词：{item.keywords.join("、")}
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>
              </Card>
            </section>
          )}

          {activeModule === "changzhou" && (
            <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
              <Card title="常州本地教育资讯" note={`${changzhouBackendStatus} · 每 5 分钟自动采集`}>
                <div className="mb-3 flex flex-wrap items-center gap-3">
                  <div
                    className={`pill px-4 py-3 text-sm flex-1 ${
                      isChangzhouBackendConnected
                        ? "border-[#a9c8ea] bg-[#164b86]/12 text-[#164b86]"
                        : "border-[#e8d6a8] bg-[#b18a4a]/14 text-[#8a5a0f]"
                    }`}
                  >
                    已聚焦升学规划业务：优先收集高考志愿、全国高校招生、综合评价、强基计划、中外合作办学等动态。
                  </div>
                  <button className="secondary-button" onClick={() => collectChangzhouNews()}>
                    立即采集
                  </button>
                </div>
                {newNewsIds.size > 0 && (
                  <div className="mb-3 pill px-4 py-2 text-sm border-[#a9c8ea] bg-[#164b86]/12 text-[#164b86]">
                    📣 本周期推送 {newNewsIds.size} 条新常州教育资讯，已高亮展示
                  </div>
                )}
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  {changzhouCategoryTabs.map((cat) => {
                    const count = changzhouCategoryCounts[cat] ?? 0;
                    const active = changzhouCategory === cat;
                    return (
                      <button
                        key={cat}
                        onClick={() => setChangzhouCategory(cat)}
                        className={`rounded-full px-3 py-1.5 text-sm font-semibold transition ${
                          active
                            ? "bg-[#164b86] text-white shadow-sm"
                            : "border border-[#d6e2f2] bg-white/80 text-[#334155] hover:bg-[#164b86]/10"
                        }`}
                      >
                        {cat}
                        <span className={active ? "ml-1 opacity-80" : "ml-1 text-[#8aa3c4]"}>{count}</span>
                      </button>
                    );
                  })}
                  <select
                    className="field ml-auto w-auto py-1.5 text-sm"
                    value={changzhouSort}
                    onChange={(e) => setChangzhouSort(e.target.value as "published" | "created" | "importance" | "relevance")}
                  >
                    <option value="published">最新发布</option>
                    <option value="created">最新采集</option>
                    <option value="importance">重要性优先</option>
                    <option value="relevance">升学规划相关性</option>
                  </select>
                </div>
                <div className="grid gap-3">
                  {displayChangzhouNews.map((item) => (
                    <ChangzhouNewsCard
                      item={item}
                      key={item.id}
                      isNew={newNewsIds.has(item.id)}
                      onOpen={() => setSelectedChangzhouNews(item)}
                      showUrl
                    />
                  ))}
                </div>
                {!displayChangzhouNews.length && (
                  <p className="card-dashed p-4 text-sm text-[#5b6b82]">
                    {changzhouCategory === "全部"
                      ? "暂无常州教育资讯。自动采集会继续按标准寻找内容。"
                      : `「${changzhouCategory}」分类下暂无资讯。`}
                  </p>
                )}
              </Card>
              <Card title="新增本地资讯" note="采集源持续接入">
                <div className="space-y-3">
                  <input className="field" placeholder="标题" value={newsForm.title} onChange={(e) => setNewsForm({ ...newsForm, title: e.target.value })} />
                  <select className="field" value={newsForm.category} onChange={(e) => setNewsForm({ ...newsForm, category: e.target.value })}>
                    {["政策文件", "校园公告", "升学规划", "招生录取", "学区划片", "考试测评", "学科竞赛", "校园开放日", "媒体报道", "小升初", "初升高", "高考"].map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <input className="field" placeholder="来源" value={newsForm.sourceName} onChange={(e) => setNewsForm({ ...newsForm, sourceName: e.target.value })} />
                  <input className="field" placeholder="链接，可空" value={newsForm.url} onChange={(e) => setNewsForm({ ...newsForm, url: e.target.value })} />
                  <textarea className="field min-h-32 resize-none" placeholder="摘要" value={newsForm.summary} onChange={(e) => setNewsForm({ ...newsForm, summary: e.target.value })} />
                  <button className="primary-button" onClick={addChangzhouNews}>入库资讯</button>
                </div>
              </Card>
            </section>
          )}

          {activeModule === "hotVideos" && (
            <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
              <div className="xl:col-span-2">
                <Card
                  title="大博主热门视频推送"
                  note={`${socialVideoBackendStatus} · 每 10 分钟自动采集`}
                >
                <div
                  className={`mb-3 pill px-4 py-3 text-sm ${
                    isSocialVideoBackendConnected
                      ? "border-[#a9c8ea] bg-[#164b86]/12 text-[#164b86]"
                      : "border-[#e8d6a8] bg-[#b18a4a]/14 text-[#8a5a0f]"
                  }`}
                >
                  凡是抖音达标的视频都会推送给你；每 10 分钟自动采集，发现新视频会高亮并通知。
                </div>
                <div className="mb-4 rounded-md border border-[#d6e2f2] bg-white/75 p-4">
                  <div className="flex flex-wrap items-start gap-2">
                    <div className="mr-auto">
                      <h3 className="font-semibold text-[#1f2d44]">点赞 / 收藏门槛</h3>
                      <p className="mt-1 text-sm text-[#5b6b82]">
                        修改后立即重算当前视频，后续自动采集按新标准推送。
                      </p>
                      <p className="mt-1 text-xs text-[#8aa3c4]">
                        {thresholdLoadError ? "门槛配置暂未连上后端" : "门槛配置已连接后端"}
                      </p>
                    </div>
                    <button
                      className="secondary-button px-3 py-2 text-sm"
                      onClick={loadHotThresholds}
                    >
                      重新读取
                    </button>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    {hotThresholds.map((item) => {
                      const key = thresholdKey(item);
                      const draft = thresholdDrafts[key] ?? {
                        likes: String(item.likes),
                        saves: String(item.saves),
                      };
                      return (
                        <section
                          className="rounded-md border border-[#e3ebf5] bg-[#f8fbff] p-3"
                          key={key}
                        >
                          <p className="text-sm font-semibold text-[#1f2d44]">
                            {thresholdLabel(item)}
                          </p>
                          <div className="mt-2 grid grid-cols-2 gap-2">
                            <label className="text-xs font-semibold text-[#5b6b82]">
                              点赞
                              <input
                                className="field mt-1"
                                min="0"
                                type="number"
                                value={draft.likes}
                                onChange={(event) =>
                                  setThresholdDrafts((current) => ({
                                    ...current,
                                    [key]: { ...draft, likes: event.target.value },
                                  }))
                                }
                              />
                            </label>
                            <label className="text-xs font-semibold text-[#5b6b82]">
                              收藏
                              <input
                                className="field mt-1"
                                min="0"
                                type="number"
                                value={draft.saves}
                                onChange={(event) =>
                                  setThresholdDrafts((current) => ({
                                    ...current,
                                    [key]: { ...draft, saves: event.target.value },
                                  }))
                                }
                              />
                            </label>
                          </div>
                        </section>
                      );
                    })}
                  </div>
                  {!hotThresholds.length && (
                    <p className="mt-3 card-dashed p-3 text-sm text-[#5b6b82]">
                      暂未读取到门槛配置，请确认后端服务已启动。
                    </p>
                  )}
                  <button
                    className="primary-button mt-3"
                    disabled={savingThresholds || !hotThresholds.length}
                    onClick={saveHotThresholds}
                  >
                    {savingThresholds ? "保存中" : "保存门槛"}
                  </button>
                </div>
                {newVideoIds.size > 0 && (
                  <div className="mb-3 flex items-center gap-3 rounded-md border border-[#164b86] bg-[#164b86]/12 px-4 py-3 text-sm font-semibold text-[#0f3a6b]">
                    <span>📣 本周期推送 {newVideoIds.size} 条新抖音爆款，已高亮展示</span>
                    <button
                      className="ml-auto rounded bg-white/70 px-2 py-1 text-xs text-[#164b86]"
                      onClick={() => setNewVideoIds(new Set())}
                    >
                      知道了
                    </button>
                  </div>
                )}
                <div className="mb-3 flex flex-wrap gap-2">
                  <button
                    className={`rounded-md px-3 py-1.5 text-sm font-semibold ${
                      hotVideoFilter === "douyinPush"
                        ? "bg-[#164b86] text-white"
                        : "border border-[#d6e2f2] bg-white/80 text-[#334155]"
                    }`}
                    onClick={() => setHotVideoFilter("douyinPush")}
                  >
                    抖音推送（{douyinPushVideos.length}）
                  </button>
                  <button
                    className={`rounded-md px-3 py-1.5 text-sm font-semibold ${
                      hotVideoFilter === "all"
                        ? "bg-[#164b86] text-white"
                        : "border border-[#d6e2f2] bg-white/80 text-[#334155]"
                    }`}
                    onClick={() => setHotVideoFilter("all")}
                  >
                    全部（{hotVideos.length}）
                  </button>
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {displayHotVideos.map((item) => (
                    <HotVideoCard
                      item={item}
                      key={item.id}
                      isNew={newVideoIds.has(item.id)}
                      showReason
                      onOpen={() => setSelectedHotVideo(item)}
                    />
                  ))}
                </div>
                {!displayHotVideos.length && (
                  <p className="card-dashed p-4 text-sm text-[#5b6b82]">
                    {hotVideoFilter === "douyinPush"
                      ? "暂无抖音达标视频。自动采集会继续按标准寻找内容。"
                      : "暂无热门视频。自动采集会继续按标准寻找内容。"}
                  </p>
                )}
                </Card>
              </div>
              <Card title="最近采集日志" note="每 10 分钟自动采集">
                <CollectionLogList logs={socialVideoLogs} />
              </Card>
              <Card title="博主池" note="符合主题的视频会自动沉淀作者">
                <div className="grid gap-3">
                  {socialCreators.map((item) => (
                    <article className="card p-3" key={item.id}>
                      <div className="flex flex-wrap gap-2">
                        <h3 className="mr-auto font-semibold">{item.name}</h3>
                        <Badge>{item.platform}</Badge>
                        <Badge>{item.category}</Badge>
                        <Badge>{item.enabled ? "启用" : "暂停"}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-[#5b6b82]">
                        {item.scope}
                      </p>
                      <input
                        className="field mt-3"
                        value={creatorKeywordDrafts[item.id] ?? item.keywords.join("，")}
                        onChange={(event) =>
                          setCreatorKeywordDrafts((current) => ({
                            ...current,
                            [item.id]: event.target.value,
                          }))
                        }
                      />
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button className="secondary-button" onClick={() => saveSocialCreator(item)}>
                          保存关键词
                        </button>
                        <button className="secondary-button" onClick={() => toggleSocialCreator(item)}>
                          {item.enabled ? "暂停采集" : "启用采集"}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
                <div className="mt-4 space-y-3 border-t border-[#e3ebf5] pt-4">
                  <input className="field" placeholder="新增博主名称" value={creatorForm.name} onChange={(e) => setCreatorForm({ ...creatorForm, name: e.target.value })} />
                  <select className="field" value={creatorForm.platform} onChange={(e) => setCreatorForm({ ...creatorForm, platform: e.target.value as SocialCreator["platform"] })}>
                    {["抖音", "微信视频号"].map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <select className="field" value={creatorForm.category} onChange={(e) => setCreatorForm({ ...creatorForm, category: e.target.value as SocialCreator["category"] })}>
                    {["高考升学", "中考升学", "常州本地教育", "家庭教育规划"].map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <select className="field" value={creatorForm.scope} onChange={(e) => setCreatorForm({ ...creatorForm, scope: e.target.value as SocialCreator["scope"] })}>
                    {["全国大博主", "常州本地"].map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <input className="field" placeholder="主页链接，可空" value={creatorForm.profileUrl} onChange={(e) => setCreatorForm({ ...creatorForm, profileUrl: e.target.value })} />
                  <input className="field" placeholder="主题关键词，逗号分隔" value={creatorForm.keywords} onChange={(e) => setCreatorForm({ ...creatorForm, keywords: e.target.value })} />
                  <button className="primary-button" onClick={addSocialCreator}>加入博主池</button>
                </div>
              </Card>
              <Card title="采集/授权入口" note="自动采集优先，人工入库仅作校验">
                <div className="space-y-3">
                  <input className="field" placeholder="视频标题" value={hotVideoForm.title} onChange={(e) => setHotVideoForm({ ...hotVideoForm, title: e.target.value })} />
                  <input className="field" placeholder="博主名称" value={hotVideoForm.creator} onChange={(e) => setHotVideoForm({ ...hotVideoForm, creator: e.target.value })} />
                  <select className="field" value={hotVideoForm.platform} onChange={(e) => setHotVideoForm({ ...hotVideoForm, platform: e.target.value as SocialHotVideo["platform"] })}>
                    {["抖音", "微信视频号"].map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <select className="field" value={hotVideoForm.scope} onChange={(e) => setHotVideoForm({ ...hotVideoForm, scope: e.target.value as SocialHotVideo["scope"] })}>
                    {["全国大博主", "常州本地"].map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <input className="field" placeholder="原视频链接，必须是完整 URL" value={hotVideoForm.url} onChange={(e) => setHotVideoForm({ ...hotVideoForm, url: e.target.value })} />
                  <div className="grid grid-cols-2 gap-2">
                    <input className="field" min="0" type="number" placeholder="点赞数" value={hotVideoForm.likes} onChange={(e) => setHotVideoForm({ ...hotVideoForm, likes: e.target.value })} />
                    <input className="field" min="0" type="number" placeholder="收藏数" value={hotVideoForm.saves} onChange={(e) => setHotVideoForm({ ...hotVideoForm, saves: e.target.value })} />
                  </div>
                  <button className="primary-button" onClick={addHotVideo}>入库并判断阈值</button>
                  <button className="secondary-button" onClick={collectPublicHotVideos}>
                    自动采集公开视频
                  </button>
                </div>
                <div className="mt-4 space-y-3 text-sm leading-6 text-[#334155]">
                  <div className="card p-3">
                    常州本地达标视频：{localHotVideos.length} 条。后续会接入账号白名单、关键词和地域判断。
                  </div>
                </div>
              </Card>
            </section>
          )}

          {activeModule === "reports" && (
            <section className="grid gap-5 xl:grid-cols-[1fr_420px]">
              <Card title="草稿审核" note="公众号文章、视频脚本、专题报告">
                <div className="grid gap-3 md:grid-cols-2">
                  {drafts.map((draft) => (
                    <article className="card p-4" key={draft.id}>
                      <div className="flex gap-2">
                        <div className="mr-auto">
                          <p className="text-xs text-[#4a5d7a]">{draft.type}</p>
                          <h3 className="font-semibold">{draft.title}</h3>
                        </div>
                        <Badge>{draft.status}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-[#5b6b82]">参考：{draft.basedOn}</p>
                      <pre className="mt-3 whitespace-pre-wrap rounded bg-white/55 p-3 text-sm">{draft.body}</pre>
                      <div className="mt-3 flex gap-2">
                        <button className="secondary-button" onClick={() => setDrafts((current) => current.map((d) => d.id === draft.id ? { ...d, status: "需修改" } : d))}>需修改</button>
                        <button className="primary-button" onClick={() => setDrafts((current) => current.map((d) => d.id === draft.id ? { ...d, status: "可发布" } : d))}>可发布</button>
                      </div>
                    </article>
                  ))}
                </div>
              </Card>
              <Card title="生成草稿" note="当前接 `/api/generate`">
                <div className="space-y-3">
                  <input className="field" placeholder="选题" value={draftTopic} onChange={(e) => setDraftTopic(e.target.value)} />
                  <div className="grid grid-cols-3 gap-2">
                    {draftTypes.map((type) => (
                      <button className="secondary-button" disabled={isGenerating} key={type} onClick={() => generateDraft(type)}>
                        {type}
                      </button>
                    ))}
                  </div>
                </div>
              </Card>
            </section>
          )}

          {activeModule === "wechat" && (
            <section className="grid gap-5 xl:grid-cols-2">
              <Card title="公众号文章转化" note="竞品文章→凭他教育原创（不抄袭、重水印）">
                <p className="mb-3 text-sm text-[#5b6b82]">
                  输入目标公众号名称，系统会搜出其近期文章；选择一篇后，自动提炼核心内容并以「凭他教育」视角重写为原创文章，原图自动去水印并叠加凭他教育水印。
                </p>
                <div className="flex gap-2">
                  <input
                    className="field flex-1"
                    placeholder="输入公众号名称，如：升学规划"
                    value={wechatAccount}
                    onChange={(e) => setWechatAccount(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const name = wechatAccount.trim();
                        if (!name) return;
                        setWechatSearching(true);
                        setWechatSearchError("");
                        searchWechatArticles(name, 12)
                          .then((items) => {
                            setWechatSearchResults(items);
                            if (!items.length) setWechatSearchError("未搜到该公众号的文章，换个名称或稍后重试");
                          })
                          .catch((err) => setWechatSearchError(String(err.message ?? err)))
                          .finally(() => setWechatSearching(false));
                      }
                    }}
                  />
                  <button
                    className="primary-button"
                    disabled={wechatSearching || !wechatAccount.trim()}
                    onClick={() => {
                      const name = wechatAccount.trim();
                      if (!name) return;
                      setWechatSearching(true);
                      setWechatSearchError("");
                      searchWechatArticles(name, 12)
                        .then((items) => {
                          setWechatSearchResults(items);
                          if (!items.length) setWechatSearchError("未搜到该公众号的文章，换个名称或稍后重试");
                        })
                        .catch((err) => setWechatSearchError(String(err.message ?? err)))
                        .finally(() => setWechatSearching(false));
                    }}
                  >
                    {wechatSearching ? "搜索中" : "搜索文章"}
                  </button>
                </div>
                {wechatSearchError && (
                  <p className="mt-3 chip-error p-2 text-sm text-[#b42323]">{wechatSearchError}</p>
                )}
                <div className="mt-4 grid gap-2">
                  {wechatSearchResults.map((item, idx) => (
                    <button
                      key={`${item.url}-${idx}`}
                      className="card-soft p-3 text-left transition hover:border-[#b6cbe8] hover:bg-white/50"
                      onClick={() => {
                        setWechatTransforming(true);
                        setWechatTransformError("");
                        setWechatResult(null);
                        transformWechatArticle(item.url, item.account_name)
                          .then((res) => setWechatResult(res))
                          .catch((err) => setWechatTransformError(String(err.message ?? err)))
                          .finally(() => setWechatTransforming(false));
                      }}
                    >
                      <p className="text-sm font-medium text-[#16243b]">{item.title}</p>
                      <p className="mt-1 text-xs text-[#64748b]">
                        {item.account_name}
                        {item.published_at ? ` · ${item.published_at}` : ""}
                      </p>
                    </button>
                  ))}
                </div>

                <div className="mt-5 border-t border-[#e3ebf6] pt-4">
                  <p className="mb-2 text-xs text-[#64748b]">
                    若搜索无结果（公众号平台偶发限流），可直接粘贴文章链接转化：
                  </p>
                  <div className="flex gap-2">
                    <input
                      id="wechat-direct-url"
                      className="field flex-1"
                      placeholder="粘贴微信公众号文章链接（mp.weixin.qq.com）"
                      onKeyDown={(e) => {
                        if (e.key !== "Enter") return;
                        const url = (e.target as HTMLInputElement).value.trim();
                        if (!url) return;
                        setWechatTransforming(true);
                        setWechatTransformError("");
                        setWechatResult(null);
                        transformWechatArticle(url)
                          .then((res) => setWechatResult(res))
                          .catch((err) => setWechatTransformError(String(err.message ?? err)))
                          .finally(() => setWechatTransforming(false));
                      }}
                    />
                    <button
                      className="secondary-button"
                      onClick={() => {
                        const el = document.getElementById("wechat-direct-url") as HTMLInputElement | null;
                        const url = el?.value.trim() ?? "";
                        if (!url) return;
                        setWechatTransforming(true);
                        setWechatTransformError("");
                        setWechatResult(null);
                        transformWechatArticle(url)
                          .then((res) => setWechatResult(res))
                          .catch((err) => setWechatTransformError(String(err.message ?? err)))
                          .finally(() => setWechatTransforming(false));
                      }}
                    >
                      转化链接
                    </button>
                  </div>
                </div>
              </Card>

              <Card title="转化结果预览" note="凭他教育风格原创稿">
                {wechatTransforming && <p className="text-sm text-[#5b6b82]">正在提炼与重写，请稍候…</p>}
                {wechatTransformError && (
                  <p className="chip-error p-2 text-sm text-[#b42323]">{wechatTransformError}</p>
                )}
                {wechatResult && !wechatTransforming && (
                  <div className="grid gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge>{wechatResult.word_count} 字</Badge>
                      <Badge>{wechatResult.images.length} 图已加水印</Badge>
                      <button
                        className="secondary-button"
                        onClick={() => {
                          navigator.clipboard?.writeText(wechatResult.body_text);
                          setNotice("已复制原文到剪贴板");
                        }}
                      >
                        复制全文
                      </button>
                      <button
                        className="secondary-button"
                        onClick={async () => {
                          setNotice("正在生成 Word，请稍候…");
                          try {
                            await downloadWechatExport(
                              wechatResult.source_url,
                              wechatResult.source_account,
                              "docx",
                            );
                            setNotice("Word 已开始下载");
                          } catch (error) {
                            setNotice(error instanceof Error ? error.message : "导出失败");
                          }
                        }}
                      >
                        下载 Word
                      </button>
                      <button
                        className="secondary-button"
                        onClick={async () => {
                          setNotice("正在生成公众号 HTML，请稍候…");
                          try {
                            await downloadWechatExport(
                              wechatResult.source_url,
                              wechatResult.source_account,
                              "wechat-html",
                            );
                            setNotice("公众号 HTML 已开始下载");
                          } catch (error) {
                            setNotice(error instanceof Error ? error.message : "导出失败");
                          }
                        }}
                      >
                        下载公众号 HTML
                      </button>
                      <button
                        className="secondary-button"
                        onClick={() => {
                          createBackendMaterial({
                            title: wechatResult.title,
                            source: "公众号" as SourceType,
                            sourceName: wechatResult.source_account || "公众号转化",
                            tags: ["公众号转化", "凭他原创"],
                            summary: wechatResult.source_title,
                            content: wechatResult.body_text,
                          })
                            .then(() => setNotice("已存入内容库"))
                            .catch((err) => setNotice(`存入失败：${err.message ?? err}`));
                        }}
                      >
                        存入内容库
                      </button>
                    </div>
                    <h3 className="text-xl font-semibold text-[#0f3a6b]">{wechatResult.title}</h3>
                    <div
                      className="prose-wechat max-h-[60vh] overflow-auto card p-4 text-[15px] leading-relaxed text-[#333]"
                      dangerouslySetInnerHTML={{ __html: wechatResult.body_html }}
                    />
                    <details className="text-sm text-[#5b6b82]">
                      <summary className="cursor-pointer">查看纯文本</summary>
                      <pre className="mt-2 whitespace-pre-wrap chip p-3">{wechatResult.body_text.replace(/\[\[CAUTION:(.*?)\]\]/g, "⚠ $1")}</pre>
                    </details>
                  </div>
                )}
                {!wechatTransforming && !wechatResult && !wechatTransformError && (
                  <p className="text-sm text-[#64748b]">在左侧搜索并选择一篇公众号文章，转化结果将显示在这里。</p>
                )}
              </Card>
            </section>
          )}

          {activeModule === "settings" && (
            <section className="grid gap-5 xl:grid-cols-2">
              <Card title="系统配置" note="当前状态">
                <StatusPanel title="AI Provider" items={[aiStatus, "默认 豆包（火山方舟）", "可切 DeepSeek / 通义千问 / 智谱GLM / Kimi（env: AI_PROVIDER）"]} />
              </Card>
              <Card title="平台授权" note="抖音/微信视频号">
                <div className="grid gap-3">
                  {(platformAuthStatus.length ? platformAuthStatus : [
                    {
                      provider: "抖音",
                      configured: false,
                      oauth_ready: false,
                      note: "后端授权状态暂不可用。",
                    },
                  ]).map((item) => (
                    <article className="card p-4" key={item.provider}>
                      <div className="flex flex-wrap gap-2">
                        <h3 className="mr-auto font-semibold">{item.provider}</h3>
                        <Badge>{item.configured ? "已配置" : "待配置"}</Badge>
                        <Badge>{item.oauth_ready ? "OAuth 可用" : "授权待接"}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-[#334155]">{item.note}</p>
                    </article>
                  ))}
                </div>
              </Card>
              <Card title="工作区备份" note="localStorage 迁移前保护数据">
                <div className="flex flex-wrap gap-2">
                  <button className="secondary-button" onClick={exportWorkspace}>导出 JSON</button>
                  <label className="secondary-button text-center">
                    导入 JSON
                    <input className="hidden" type="file" accept="application/json,.json" onChange={(e) => importWorkspace(e.target.files?.[0])} />
                  </label>
                  <button className="danger-button" onClick={resetDemo}>恢复演示</button>
                </div>
              </Card>
            </section>
          )}
        </section>
      </div>
      {selectedChangzhouNews && (
        <ChangzhouNewsDetail
          item={selectedChangzhouNews}
          onClose={() => setSelectedChangzhouNews(null)}
        />
      )}
      {selectedHotVideo && (
        <HotVideoDetail
          item={selectedHotVideo}
          isGeneratingTranscript={transcribingVideoId === selectedHotVideo.id}
          onClose={() => setSelectedHotVideo(null)}
          onGenerateTranscript={() => generateHotVideoTranscript(selectedHotVideo)}
          onGenerateManuscript={() => generateHotVideoManuscript(selectedHotVideo)}
          onSaveToLibrary={() => saveManuscriptToLibrary(selectedHotVideo)}
        />
      )}
    </main>
  );
}

function HotVideoCard({
  item,
  onOpen,
  showReason = false,
  isNew = false,
}: {
  item: SocialHotVideo;
  onOpen: () => void;
  showReason?: boolean;
  isNew?: boolean;
}) {
  const hasEngagement = item.likes > 0 || item.saves > 0;
  const isPushed = item.platform === "抖音" && item.isHot;

  function handleKeyDown(event: React.KeyboardEvent<HTMLElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpen();
    }
  }

  return (
    <article
      aria-label={`打开热门视频：${item.title}`}
      className={`cursor-pointer card p-4 transition hover:border-[#164b86] hover:bg-[#f1f7fd] focus:outline-none focus:ring-2 focus:ring-[#164b86] ${
        isNew ? "border-[#164b86] ring-2 ring-[#164b86]" : "border-[#d6e2f2]"
      }`}
      onClick={onOpen}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
    >
      <div className="flex flex-wrap gap-2">
        <h3 className="mr-auto font-semibold">{item.title}</h3>
        {isPushed && (
          <span className="rounded bg-[#164b86] px-2 py-1 text-xs font-semibold text-white">
            已推送
          </span>
        )}
        {isNew && (
          <span className="rounded bg-[#a8420f] px-2 py-1 text-xs font-semibold text-white">
            新
          </span>
        )}
        <Badge>{item.platform}</Badge>
        <Badge>{item.scope}</Badge>
        <Badge>{item.recommendationScore.toLocaleString()}分</Badge>
      </div>
      <p className="mt-2 text-sm text-[#334155]">{item.creator}</p>
      {hasEngagement ? (
        <p className="mt-2 text-sm font-semibold text-[#164b86]">
          {item.likes.toLocaleString()}赞 · {item.saves.toLocaleString()}收藏
        </p>
      ) : null}
      <p className="mt-2 text-xs text-[#5b6b82]">{item.threshold}</p>
      {showReason && hasEngagement && (
        <p className="mt-2 text-sm leading-6 text-[#334155]">{item.reason}</p>
      )}
      <p className="mt-3 text-sm font-semibold text-[#164b86]">点击查看详情</p>
    </article>
  );
}

function HotVideoDetail({
  item,
  isGeneratingTranscript,
  onClose,
  onGenerateTranscript,
  onGenerateManuscript,
  onSaveToLibrary,
}: {
  item: SocialHotVideo;
  isGeneratingTranscript: boolean;
  onClose: () => void;
  onGenerateTranscript: () => void;
  onGenerateManuscript: () => void;
  onSaveToLibrary: () => void;
}) {
  const hasEngagement = item.likes > 0 || item.saves > 0;
  const [noticeLocal, setNoticeLocal] = useState("");

  function copyManuscript() {
    if (!item.manuscript) return;
    if (!navigator.clipboard) {
      setNoticeLocal("当前环境不支持自动复制，请手动选择");
      return;
    }
    navigator.clipboard.writeText(item.manuscript).then(
      () => setNoticeLocal("文稿已复制"),
      () => setNoticeLocal("复制失败，请手动选择"),
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/20 p-4 md:p-6" onClick={onClose} role="presentation">
      <section
        aria-label="热门视频详情"
        className="ml-auto flex h-full max-w-xl flex-col overflow-y-auto rounded-md border border-[#d6e2f2] bg-white/80 backdrop-blur-2xl p-5 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex gap-3 border-b border-[#e3ebf5] pb-4">
          <div className="mr-auto">
            <p className="text-sm font-semibold text-[#4a5d7a]">热门视频推送</p>
            <h2 className="mt-2 text-2xl font-semibold">{item.title}</h2>
          </div>
          <button className="secondary-button h-10" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge>{item.platform}</Badge>
          <Badge>{item.scope}</Badge>
          <Badge>{item.creator}</Badge>
          <Badge>{item.recommendationScore.toLocaleString()}分</Badge>
        </div>
        {hasEngagement && (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <MetricBox label="点赞" value={item.likes.toLocaleString()} />
            <MetricBox label="收藏" value={item.saves.toLocaleString()} />
          </div>
        )}
        <ThresholdLine label="命中规则" value={item.threshold} />
        <ThresholdLine label="推荐排序分" value={`${item.recommendationScore.toLocaleString()} 分`} />
        {hasEngagement && (
          <p className="mt-4 whitespace-pre-wrap chip p-4 text-sm leading-6 text-[#334155]">
            {item.reason}
          </p>
        )}
        <p className="mt-4 text-sm text-[#5b6b82]">发布时间：{item.publishedAt}</p>
        <div className="mt-4 card p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="mr-auto font-semibold">视频转文字 · 文稿</h3>
            {item.transcriptSource ? <Badge>{item.transcriptSource}</Badge> : null}
          </div>
          <ol className="mt-3 space-y-3 text-sm">
            <li>
              <p className="font-semibold text-[#164b86]">① 语音转文字（原始转写）</p>
              <p className="mt-1 text-xs text-[#5b6b82]">
                优先读取抖音自带字幕/画面文字（无需 OpenAI）；无字幕的视频需配置语音识别服务方可转写。
              </p>
            </li>
            <li>
              <p className="font-semibold text-[#164b86]">② 去语气词（清洗稿）</p>
              {item.transcript ? (
                <p className="mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap chip p-3 leading-6 text-[#1f2d44]">
                  {item.transcript}
                </p>
              ) : (
                <p className="mt-1 text-xs text-[#5b6b82]">尚未提取。</p>
              )}
            </li>
            <li>
              <p className="font-semibold text-[#164b86]">③ 生成文稿</p>
              {item.manuscript ? (
                <p className="mt-1 max-h-60 overflow-y-auto whitespace-pre-wrap chip p-3 leading-6 text-[#0f3a6b]">
                  {item.manuscript}
                </p>
              ) : (
                <p className="mt-1 text-xs text-[#5b6b82]">
                  尚未生成。点击“生成文稿”会先做语音转文字、再去语气词，最后整理成通顺文稿。
                </p>
              )}
            </li>
          </ol>
          {item.transcriptUpdatedAt ? (
            <p className="mt-2 text-xs text-[#5b6b82]">更新时间：{item.transcriptUpdatedAt}</p>
          ) : null}
          {noticeLocal ? <p className="mt-2 text-xs text-[#164b86]">{noticeLocal}</p> : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              className="secondary-button"
              disabled={isGeneratingTranscript}
              onClick={onGenerateTranscript}
            >
              {isGeneratingTranscript ? "处理中" : item.transcript ? "重新提取转写" : "提取转写"}
            </button>
            <button
              className="secondary-button"
              disabled={isGeneratingTranscript || !item.transcript}
              onClick={onGenerateManuscript}
            >
              生成文稿
            </button>
            <button
              className="secondary-button"
              disabled={!item.manuscript}
              onClick={copyManuscript}
            >
              复制文稿
            </button>
            <button
              className="primary-button"
              disabled={!item.manuscript}
              onClick={onSaveToLibrary}
            >
              存入内容库
            </button>
          </div>
        </div>
        {item.url ? (
          <a className="primary-button mt-4 text-center" href={item.url} rel="noreferrer" target="_blank">
            打开视频
          </a>
        ) : (
          <p className="mt-4 card-dashed p-3 text-sm text-[#5b6b82]">
            这条视频暂无原始链接，后续接入采集源后自动回填。
          </p>
        )}
      </section>
    </div>
  );
}

function CollectionLogList({ logs }: { logs: SocialVideoCollectionLog[] }) {
  if (!logs.length) {
    return (
      <p className="card-dashed p-4 text-sm text-[#5b6b82]">
        暂无采集日志。点击自动采集后会记录本轮发现、过滤和入库数量。
      </p>
    );
  }

  return (
    <div className="grid gap-3">
      {logs.slice(0, 5).map((log) => (
        <article className="card p-3" key={log.id}>
          <div className="flex flex-wrap gap-2">
            <h3 className="mr-auto text-sm font-semibold">{log.status}</h3>
            <Badge>新增 {log.created}</Badge>
          </div>
          <p className="mt-2 text-sm leading-6 text-[#334155]">{log.message}</p>
          <p className="mt-2 text-xs text-[#5b6b82]">{log.finishedAt}</p>
        </article>
      ))}
    </div>
  );
}

function ThresholdLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 card p-3">
      <span className="mr-auto font-semibold">{label}</span>
      <span className="text-[#164b86]">{value}</span>
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-3">
      <p className="text-sm text-[#5b6b82]">{label}</p>
      <p className="mt-1 font-academic text-2xl font-semibold text-[#164b86]">{value}</p>
    </div>
  );
}

function ChangzhouNewsCard({
  item,
  onOpen,
  showUrl = false,
  isNew = false,
}: {
  item: ChangzhouNews;
  onOpen: () => void;
  showUrl?: boolean;
  isNew?: boolean;
}) {
  function handleKeyDown(event: React.KeyboardEvent<HTMLElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpen();
    }
  }

  return (
    <article
      aria-label={`打开常州资讯：${item.title}`}
      className={`card cursor-pointer p-4 transition focus:outline-none focus:ring-2 focus:ring-[#164b86] ${
        isNew
          ? "border-[#164b86] bg-[#164b86]/10 shadow-[0_0_0_2px_rgba(22,75,134,0.25)] hover:bg-[#164b86]/15"
          : "hover:border-[#164b86] hover:bg-[#f1f7fd]"
      }`}
      onClick={onOpen}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto font-semibold">{item.title}</h3>
        {isNew && (
          <span className="rounded-full bg-[#164b86] px-2 py-0.5 text-xs font-semibold text-white">新</span>
        )}
        <Badge>{item.category}</Badge>
        <Badge>{item.importance}</Badge>
      </div>
      <div className="mt-3 rounded-md border border-[#d6e2f2] bg-white/70 p-3">
        <p className="text-xs font-semibold text-[#8a5a0f]">内容提示</p>
        <p className="mt-1 text-sm leading-6 text-[#334155]">
          {buildChangzhouNewsPrompt(item)}
        </p>
      </div>
      <p className="mt-2 text-xs text-[#5b6b82]">
        {item.sourceName} · {item.publishedAt}
      </p>
      {showUrl && item.url && <p className="mt-2 break-all text-xs text-[#5b6b82]">{item.url}</p>}
      <p className="mt-3 text-sm font-semibold text-[#164b86]">点击查看详情</p>
    </article>
  );
}

function ChangzhouNewsDetail({
  item,
  onClose,
}: {
  item: ChangzhouNews;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 bg-black/20 p-4 md:p-6"
      onClick={onClose}
      role="presentation"
    >
      <section
        aria-label="常州资讯详情"
        className="ml-auto flex h-full max-w-xl flex-col overflow-y-auto rounded-md border border-[#d6e2f2] bg-white/80 backdrop-blur-2xl p-5 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex gap-3 border-b border-[#e3ebf5] pb-4">
          <div className="mr-auto">
            <p className="text-sm font-semibold text-[#4a5d7a]">常州本地教育资讯</p>
            <h2 className="mt-2 text-2xl font-semibold">{item.title}</h2>
          </div>
          <button className="secondary-button h-10" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge>{item.category}</Badge>
          <Badge>{item.importance}</Badge>
          <Badge>{item.sourceName}</Badge>
        </div>
        <p className="mt-4 text-sm text-[#5b6b82]">发布时间：{item.publishedAt}</p>
        <p className="mt-4 whitespace-pre-wrap chip p-4 text-sm leading-6 text-[#334155]">
          {item.summary || "暂无摘要"}
        </p>
        {item.url ? (
          <a className="primary-button mt-4 text-center" href={item.url} rel="noreferrer" target="_blank">
            打开原文
          </a>
        ) : (
          <p className="mt-4 card-dashed p-3 text-sm text-[#5b6b82]">
            这条资讯暂无原文链接。
          </p>
        )}
      </section>
    </div>
  );
}

function Card({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <section className="card p-4">
      <div className="card-head">
        <h2 className="card-title">{title}</h2>
        {note ? <p className="card-note">{note}</p> : null}
      </div>
      {children}
    </section>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return <span className="rounded bg-[#164b86]/10 px-2 py-1 text-xs text-[#82602a]">{children}</span>;
}

function StatusPanel({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="card p-4">
      <h3 className="font-semibold">{title}</h3>
      <ul className="mt-3 space-y-2 text-sm text-[#334155]">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function Placeholder({ title, lines }: { title: string; lines: string[] }) {
  return (
    <Card title={title} note="生产模块入口">
      <div className="card-dashed p-5">
        <ul className="space-y-2 text-sm leading-6 text-[#334155]">
          {lines.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </div>
    </Card>
  );
}
