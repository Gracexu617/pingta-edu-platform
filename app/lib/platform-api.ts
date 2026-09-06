import {
  buildWorkspaceBackup,
  parseWorkspaceBackup,
  seedDrafts,
  seedMaterials,
  seedSources,
  seedTasks,
  storageKey,
  type CollectTask,
  type Draft,
  type Influencer,
  type InfluencerPlatform,
  type ChangzhouNews,
  type Material,
  type SourceRecord,
  type SourceType,
  type SocialCreator,
  type SocialHotVideo,
  type SocialVideoCollectionLog,
} from "./workspace";

export type WorkspaceSnapshot = {
  sources: SourceRecord[];
  tasks: CollectTask[];
  materials: Material[];
  drafts: Draft[];
};

export type CreateSourceInput = Pick<SourceRecord, "name" | "type" | "url" | "note">;
export type UpdateTaskInput = Pick<CollectTask, "status">;
export type CreateDocumentInput = Pick<
  Material,
  "title" | "source" | "sourceName" | "taskId" | "tags" | "summary" | "content"
>;

export type PlatformApi = {
  loadWorkspace(): WorkspaceSnapshot;
  saveWorkspace(snapshot: WorkspaceSnapshot): void;
  createSource(input: CreateSourceInput): SourceRecord;
  createTask(source: SourceRecord): CollectTask;
  createDocument(input: CreateDocumentInput): Material;
  updateTask(task: CollectTask, input: UpdateTaskInput): CollectTask;
};

type BackendSource = {
  id: number;
  name: string;
  type: SourceType;
  url: string;
  note: string;
  status: SourceRecord["status"];
};

type BackendSourceList = {
  items: BackendSource[];
};

type BackendMaterial = {
  id: number;
  title: string;
  source: SourceType;
  source_name: string | null;
  source_id: number | null;
  url: string;
  tags: string[];
  keywords: string[];
  summary: string;
  content: string;
  status: Material["status"];
};

type BackendMaterialList = {
  items: BackendMaterial[];
};

type BackendCollectTask = {
  id: number;
  source_id: number;
  source_name: string;
  source_type: SourceType;
  url: string;
  goal: string;
  status: CollectTask["status"];
  created_at: string;
};

type BackendCollectTaskList = {
  items: BackendCollectTask[];
};

type BackendTaskExecution = {
  task: BackendCollectTask;
  material: BackendMaterial;
};

type BackendInfluencer = {
  id: number;
  name: string;
  platform: InfluencerPlatform;
  profile_url: string;
  note: string;
  core_views: string[];
  style_traits: string[];
  common_topics: string[];
  parent_questions: string[];
  content_count: number;
};

type BackendInfluencerList = {
  items: BackendInfluencer[];
};

type BackendInfluencerDistill = {
  influencer: BackendInfluencer;
};

type BackendSearchResponse = {
  query: string;
  total: number;
  items: BackendMaterial[];
};

type BackendChangzhouNews = {
  id: number;
  title: string;
  category: string;
  source_name: string;
  url: string;
  summary: string;
  importance: ChangzhouNews["importance"];
  published_at: string | null;
  created_at: string;
};

type BackendChangzhouNewsList = {
  items: BackendChangzhouNews[];
};

type BackendSocialVideo = {
  id: number;
  title: string;
  creator: string;
  platform: SocialHotVideo["platform"];
  scope: SocialHotVideo["scope"];
  original_url: string;
  likes: number;
  saves: number;
  threshold: string;
  is_hot: boolean;
  reason: string;
  recommendation_score: number;
  transcript: string;
  transcript_source: string;
  transcript_updated_at: string | null;
  manuscript: string;
  published_at: string;
  collected_at: string;
};

type BackendSocialVideoList = {
  items: BackendSocialVideo[];
};

type BackendSocialVideoCollectionLog = {
  id: number;
  started_at: string;
  finished_at: string;
  discovered: number;
  hot_matched: number;
  scope_rejected: number;
  duplicate_skipped: number;
  created: number;
  status: string;
  message: string;
};

type BackendSocialVideoCollectionLogList = {
  items: BackendSocialVideoCollectionLog[];
};

type BackendSocialCreator = {
  id: number;
  name: string;
  platform: SocialCreator["platform"];
  scope: SocialCreator["scope"];
  category: SocialCreator["category"];
  profile_url: string;
  keywords: string[];
  enabled: boolean;
};

type BackendSocialCreatorList = {
  items: BackendSocialCreator[];
};

export type PlatformAuthProvider = {
  provider: string;
  configured: boolean;
  oauth_ready: boolean;
  note: string;
};

const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";
const accessPasswordStorageKey = "pingta-platform-access-password";

export function getStoredAccessPassword(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(accessPasswordStorageKey) ?? "";
}

export function setStoredAccessPassword(password: string): void {
  if (typeof window === "undefined") return;
  const cleaned = password.trim();
  if (cleaned) {
    window.localStorage.setItem(accessPasswordStorageKey, cleaned);
  } else {
    window.localStorage.removeItem(accessPasswordStorageKey);
  }
}

function backendHeaders(headers: HeadersInit = {}): HeadersInit {
  const password = getStoredAccessPassword();
  return password ? { ...headers, "X-App-Password": password } : headers;
}

function toSourceRecord(source: BackendSource): SourceRecord {
  return {
    id: source.id,
    name: source.name,
    type: source.type,
    url: source.url,
    note: source.note,
    status: source.status,
  };
}

function toMaterial(material: BackendMaterial): Material {
  return {
    id: material.id,
    title: material.title,
    source: material.source,
    sourceName: material.source_name ?? undefined,
    taskId: undefined,
    tags: material.tags,
    keywords: material.keywords,
    summary: material.summary,
    content: material.content,
    status: material.status,
  };
}

function toCollectTask(task: BackendCollectTask): CollectTask {
  return {
    id: task.id,
    sourceId: task.source_id,
    sourceName: task.source_name,
    sourceType: task.source_type,
    url: task.url,
    goal: task.goal,
    status: task.status,
    createdAt: new Date(task.created_at).toLocaleString("zh-CN", { hour12: false }),
  };
}

function toInfluencer(item: BackendInfluencer): Influencer {
  return {
    id: item.id,
    name: item.name,
    platform: item.platform,
    profileUrl: item.profile_url,
    note: item.note,
    coreViews: item.core_views,
    styleTraits: item.style_traits,
    commonTopics: item.common_topics,
    parentQuestions: item.parent_questions,
    contentCount: item.content_count,
  };
}

function toChangzhouNews(item: BackendChangzhouNews): ChangzhouNews {
  return {
    id: item.id,
    title: item.title,
    category: item.category,
    sourceName: item.source_name,
    url: item.url,
    summary: item.summary,
    importance: item.importance,
    publishedAt: item.published_at
      ? new Date(item.published_at).toLocaleString("zh-CN", { hour12: false })
      : "日期未知",
    createdAt: new Date(item.created_at).toLocaleString("zh-CN", { hour12: false }),
  };
}

function toSocialHotVideo(item: BackendSocialVideo): SocialHotVideo {
  return {
    id: item.id,
    title: item.title,
    creator: item.creator,
    platform: item.platform,
    scope: item.scope,
    likes: item.likes,
    saves: item.saves,
    isHot: item.is_hot,
    threshold: item.threshold,
    reason: item.reason,
    recommendationScore: item.recommendation_score,
    transcript: item.transcript,
    transcriptSource: item.transcript_source,
    transcriptUpdatedAt: item.transcript_updated_at,
    manuscript: item.manuscript ?? "",
    url: item.original_url,
    publishedAt: new Date(item.published_at).toLocaleString("zh-CN", { hour12: false }),
  };
}

function toSocialVideoCollectionLog(item: BackendSocialVideoCollectionLog): SocialVideoCollectionLog {
  return {
    id: item.id,
    startedAt: new Date(item.started_at).toLocaleString("zh-CN", { hour12: false }),
    finishedAt: new Date(item.finished_at).toLocaleString("zh-CN", { hour12: false }),
    discovered: item.discovered,
    hotMatched: item.hot_matched,
    scopeRejected: item.scope_rejected,
    duplicateSkipped: item.duplicate_skipped,
    created: item.created,
    status: item.status,
    message: item.message,
  };
}

function toSocialCreator(item: BackendSocialCreator): SocialCreator {
  return {
    id: item.id,
    name: item.name,
    platform: item.platform,
    scope: item.scope,
    category: item.category,
    profileUrl: item.profile_url,
    keywords: item.keywords,
    enabled: item.enabled,
  };
}

async function parseBackendResponse<T>(response: Response): Promise<T> {
  const data = (await response.json()) as T & { detail?: string };
  if (!response.ok) {
    throw new Error(data.detail ?? `Request failed: ${response.status}`);
  }
  return data;
}

export async function listBackendSources(): Promise<SourceRecord[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/sources`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendSourceList>(response);
  return data.items.map(toSourceRecord);
}

export async function createBackendSource(input: CreateSourceInput): Promise<SourceRecord> {
  const response = await fetch(`${backendBaseUrl}/api/v1/sources`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify(input),
  });
  return toSourceRecord(await parseBackendResponse<BackendSource>(response));
}

export async function updateBackendSource(
  source: SourceRecord,
  input: Partial<CreateSourceInput> & Pick<SourceRecord, "status">,
): Promise<SourceRecord> {
  const response = await fetch(`${backendBaseUrl}/api/v1/sources/${source.id}`, {
    method: "PATCH",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify(input),
  });
  return toSourceRecord(await parseBackendResponse<BackendSource>(response));
}

export async function listBackendMaterials(): Promise<Material[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/materials`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendMaterialList>(response);
  return data.items.map(toMaterial);
}

export async function createBackendMaterial(input: CreateDocumentInput): Promise<Material> {
  const response = await fetch(`${backendBaseUrl}/api/v1/materials`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({
      title: input.title,
      source: input.source,
      source_name: input.sourceName,
      tags: input.tags,
      summary: input.summary,
      content: input.content,
    }),
  });
  return toMaterial(await parseBackendResponse<BackendMaterial>(response));
}

export async function updateBackendMaterial(
  material: Material,
  input: Partial<Pick<Material, "title" | "tags" | "summary" | "content" | "status">>,
): Promise<Material> {
  const response = await fetch(`${backendBaseUrl}/api/v1/materials/${material.id}`, {
    method: "PATCH",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify(input),
  });
  return toMaterial(await parseBackendResponse<BackendMaterial>(response));
}

export async function processBackendMaterial(material: Material): Promise<Material> {
  const response = await fetch(`${backendBaseUrl}/api/v1/materials/${material.id}/process`, {
    method: "POST",
    headers: backendHeaders({ Accept: "application/json" }),
  });
  return toMaterial(await parseBackendResponse<BackendMaterial>(response));
}

export async function listBackendTasks(): Promise<CollectTask[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/collect-tasks`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendCollectTaskList>(response);
  return data.items.map(toCollectTask);
}

export async function createBackendTask(source: SourceRecord): Promise<CollectTask> {
  const response = await fetch(`${backendBaseUrl}/api/v1/collect-tasks`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({ source_id: source.id }),
  });
  return toCollectTask(await parseBackendResponse<BackendCollectTask>(response));
}

export async function updateBackendTask(
  task: CollectTask,
  input: UpdateTaskInput,
): Promise<CollectTask> {
  const response = await fetch(`${backendBaseUrl}/api/v1/collect-tasks/${task.id}`, {
    method: "PATCH",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify(input),
  });
  return toCollectTask(await parseBackendResponse<BackendCollectTask>(response));
}

export async function executeBackendTask(task: CollectTask): Promise<{
  task: CollectTask;
  material: Material;
}> {
  const response = await fetch(`${backendBaseUrl}/api/v1/collect-tasks/${task.id}/execute`, {
    method: "POST",
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendTaskExecution>(response);
  return {
    task: toCollectTask(data.task),
    material: toMaterial(data.material),
  };
}

export async function listBackendInfluencers(): Promise<Influencer[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/influencers`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendInfluencerList>(response);
  return data.items.map(toInfluencer);
}

export async function createBackendInfluencer(input: {
  name: string;
  platform: InfluencerPlatform;
  profileUrl: string;
  note: string;
}): Promise<Influencer> {
  const response = await fetch(`${backendBaseUrl}/api/v1/influencers`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({
      name: input.name,
      platform: input.platform,
      profile_url: input.profileUrl,
      note: input.note,
    }),
  });
  return toInfluencer(await parseBackendResponse<BackendInfluencer>(response));
}

export async function distillBackendInfluencerContent(input: {
  influencerId: number;
  title: string;
  url: string;
  content: string;
}): Promise<Influencer> {
  const response = await fetch(`${backendBaseUrl}/api/v1/influencers/${input.influencerId}/contents`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({ title: input.title, url: input.url, content: input.content }),
  });
  const data = await parseBackendResponse<BackendInfluencerDistill>(response);
  return toInfluencer(data.influencer);
}

export async function searchBackendMaterials(query: string): Promise<Material[]> {
  const params = new URLSearchParams({ q: query });
  const response = await fetch(`${backendBaseUrl}/api/v1/search?${params.toString()}`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendSearchResponse>(response);
  return data.items.map(toMaterial);
}

export async function listBackendChangzhouNews(): Promise<ChangzhouNews[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/changzhou-news`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendChangzhouNewsList>(response);
  return data.items.map(toChangzhouNews);
}

export async function createBackendChangzhouNews(input: {
  title: string;
  category: string;
  sourceName: string;
  url: string;
  summary: string;
}): Promise<ChangzhouNews> {
  const response = await fetch(`${backendBaseUrl}/api/v1/changzhou-news`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({
      title: input.title,
      category: input.category,
      source_name: input.sourceName,
      url: input.url,
      summary: input.summary,
    }),
  });
  return toChangzhouNews(await parseBackendResponse<BackendChangzhouNews>(response));
}

export async function collectBackendChangzhouNews(): Promise<{
  discovered: number;
  duplicateSkipped: number;
  created: number;
}> {
  const response = await fetch(`${backendBaseUrl}/api/v1/changzhou-news/collect`, {
    method: "POST",
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<{
    discovered: number;
    duplicate_skipped: number;
    created: number;
  }>(response);
  return {
    discovered: data.discovered,
    duplicateSkipped: data.duplicate_skipped,
    created: data.created,
  };
}

export async function listBackendSocialVideos(): Promise<SocialHotVideo[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-videos`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendSocialVideoList>(response);
  return data.items.map(toSocialHotVideo);
}

export async function createBackendSocialVideo(input: {
  title: string;
  creator: string;
  platform: SocialHotVideo["platform"];
  scope: SocialHotVideo["scope"];
  url: string;
  likes: number;
  saves: number;
}): Promise<SocialHotVideo> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-videos`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({
      title: input.title,
      creator: input.creator,
      platform: input.platform,
      scope: input.scope,
      original_url: input.url,
      likes: input.likes,
      saves: input.saves,
    }),
  });
  return toSocialHotVideo(await parseBackendResponse<BackendSocialVideo>(response));
}

export async function collectBackendPublicSocialVideos(): Promise<SocialHotVideo[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-videos/collect-public`, {
    method: "POST",
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<{ created: number; items: BackendSocialVideo[] }>(response);
  return data.items.map(toSocialHotVideo);
}

export async function listBackendSocialVideoCollectionLogs(): Promise<SocialVideoCollectionLog[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-videos/collection-logs`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendSocialVideoCollectionLogList>(response);
  return data.items.map(toSocialVideoCollectionLog);
}

export async function generateBackendSocialVideoTranscript(videoId: number): Promise<SocialHotVideo> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-videos/${videoId}/transcript`, {
    method: "POST",
    headers: backendHeaders({ Accept: "application/json" }),
  });
  return toSocialHotVideo(await parseBackendResponse<BackendSocialVideo>(response));
}

export async function generateBackendSocialVideoManuscript(videoId: number): Promise<SocialHotVideo> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-videos/${videoId}/manuscript`, {
    method: "POST",
    headers: backendHeaders({ Accept: "application/json" }),
  });
  return toSocialHotVideo(await parseBackendResponse<BackendSocialVideo>(response));
}

export type HotThreshold = {
  platform: SocialHotVideo["platform"];
  scope: SocialHotVideo["scope"];
  likes: number;
  saves: number;
};

/** 读取当前 4 个（平台 × 范围）组合的推送门槛。 */
export async function getHotThresholds(): Promise<HotThreshold[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-videos/hot-thresholds`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<{ items: HotThreshold[] }>(response);
  return data.items;
}

/** 保存推送门槛（4 个组合），后端会按新标准重算所有已采集视频的 is_hot。 */
export async function putHotThresholds(items: HotThreshold[]): Promise<HotThreshold[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-videos/hot-thresholds`, {
    method: "PUT",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({ items }),
  });
  const data = await parseBackendResponse<{ items: HotThreshold[] }>(response);
  return data.items;
}

export async function getBackendPlatformAuthStatus(): Promise<PlatformAuthProvider[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/platform-auth/status`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<{ providers: PlatformAuthProvider[] }>(response);
  return data.providers;
}

export async function listBackendSocialCreators(): Promise<SocialCreator[]> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-creators`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<BackendSocialCreatorList>(response);
  return data.items.map(toSocialCreator);
}

export async function createBackendSocialCreator(input: {
  name: string;
  platform: SocialCreator["platform"];
  scope: SocialCreator["scope"];
  category: SocialCreator["category"];
  profileUrl: string;
  keywords: string[];
}): Promise<SocialCreator> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-creators`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({
      name: input.name,
      platform: input.platform,
      scope: input.scope,
      category: input.category,
      profile_url: input.profileUrl,
      keywords: input.keywords,
    }),
  });
  return toSocialCreator(await parseBackendResponse<BackendSocialCreator>(response));
}

export async function updateBackendSocialCreator(
  creator: SocialCreator,
  input: Partial<
    Pick<SocialCreator, "platform" | "scope" | "category" | "profileUrl" | "keywords" | "enabled">
  >,
): Promise<SocialCreator> {
  const response = await fetch(`${backendBaseUrl}/api/v1/social-creators/${creator.id}`, {
    method: "PATCH",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({
      platform: input.platform,
      scope: input.scope,
      category: input.category,
      profile_url: input.profileUrl,
      keywords: input.keywords,
      enabled: input.enabled,
    }),
  });
  return toSocialCreator(await parseBackendResponse<BackendSocialCreator>(response));
}

// ── 公众号文章转化 ────────────────────────────────────────────────────────

export type WechatSearchItem = {
  title: string;
  url: string;
  summary: string;
  account_name: string;
  published_at: string;
};

export type WechatSearchResponse = {
  items: WechatSearchItem[];
  total: number;
};

export type WechatTransformedImage = {
  url: string;
  alt_text: string;
  has_processed_data: boolean;
};

export type WechatTransformResponse = {
  title: string;
  body_html: string;
  body_text: string;
  images: WechatTransformedImage[];
  source_account: string;
  source_title: string;
  source_url: string;
  word_count: number;
  transformed_at: string;
};

export async function searchWechatArticles(
  accountName: string,
  limit = 10,
): Promise<WechatSearchItem[]> {
  const params = new URLSearchParams({ account_name: accountName, limit: String(limit) });
  const response = await fetch(`${backendBaseUrl}/api/v1/wechat/search?${params.toString()}`, {
    headers: backendHeaders({ Accept: "application/json" }),
  });
  const data = await parseBackendResponse<WechatSearchResponse>(response);
  return data.items;
}

export async function transformWechatArticle(
  articleUrl: string,
  accountName = "",
): Promise<WechatTransformResponse> {
  const response = await fetch(`${backendBaseUrl}/api/v1/wechat/transform`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
    body: JSON.stringify({ article_url: articleUrl, account_name: accountName }),
  });
  return parseBackendResponse<WechatTransformResponse>(response);
}

/** 生成公众号文章的 Word / 公众号 HTML 导出链接（后端会重新转化并返回文件）。 */
export function wechatExportUrl(
  articleUrl: string,
  accountName: string,
  kind: "docx" | "wechat-html",
): string {
  const params = new URLSearchParams({
    article_url: articleUrl,
    account_name: accountName ?? "",
  });
  return `${backendBaseUrl}/api/v1/wechat/export/${kind}?${params.toString()}`;
}

/** 触发浏览器下载导出文件。 */
export async function downloadWechatExport(
  articleUrl: string,
  accountName: string,
  kind: "docx" | "wechat-html",
): Promise<void> {
  const url = wechatExportUrl(articleUrl, accountName, kind);
  const response = await fetch(url, {
    headers: backendHeaders({ Accept: "*/*" }),
  });
  if (!response.ok) {
    throw new Error(`导出失败：${response.status}`);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = kind === "docx" ? "wechat-article.docx" : "wechat-article.html";
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}

export const emptyWorkspace: WorkspaceSnapshot = {
  sources: seedSources,
  tasks: seedTasks,
  materials: seedMaterials,
  drafts: seedDrafts,
};

export function loadWorkspaceSnapshot(): WorkspaceSnapshot {
  if (typeof window === "undefined") return emptyWorkspace;
  const raw = window.localStorage.getItem(storageKey);
  if (!raw) return emptyWorkspace;
  const backup = parseWorkspaceBackup(raw);
  if (!backup) return emptyWorkspace;
  return {
    sources: backup.sources,
    tasks: backup.tasks,
    materials: backup.materials,
    drafts: backup.drafts,
  };
}

export function saveWorkspaceSnapshot(snapshot: WorkspaceSnapshot): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey, JSON.stringify(buildWorkspaceBackup(snapshot)));
}

export const localPlatformApi: PlatformApi = {
  loadWorkspace: loadWorkspaceSnapshot,
  saveWorkspace: saveWorkspaceSnapshot,

  createSource(input) {
    return {
      id: Date.now(),
      ...input,
      status: "启用",
    };
  },

  createTask(source) {
    return {
      id: Date.now(),
      sourceId: source.id,
      sourceName: source.name,
      sourceType: source.type,
      url: source.url,
      goal: source.note || `采集${source.name}的新内容`,
      status: "待采集",
      createdAt: new Date().toLocaleString("zh-CN", { hour12: false }),
    };
  },

  createDocument(input) {
    return {
      id: Date.now(),
      status: "待整理",
      ...input,
    };
  },

  updateTask(task, input) {
    return { ...task, ...input };
  },
};
