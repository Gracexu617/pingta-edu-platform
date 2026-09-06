export type SourceType = "公众号" | "视频号" | "高校官网" | "教育资讯" | "手动资料";
export type DraftType = "公众号文章" | "视频号脚本" | "专业文章";
export type InfluencerPlatform = "公众号" | "视频号" | "其他";

export type Influencer = {
  id: number;
  name: string;
  platform: InfluencerPlatform;
  profileUrl: string;
  note: string;
  coreViews: string[];
  styleTraits: string[];
  commonTopics: string[];
  parentQuestions: string[];
  contentCount: number;
};

export type ChangzhouNews = {
  id: number;
  title: string;
  category: string;
  sourceName: string;
  url: string;
  summary: string;
  importance: "普通" | "重要" | "重大";
  publishedAt: string;
  createdAt: string;
};

export type SocialHotVideo = {
  id: number;
  title: string;
  creator: string;
  platform: "抖音" | "微信视频号";
  scope: "全国大博主" | "常州本地";
  likes: number;
  saves: number;
  isHot: boolean;
  threshold: string;
  reason: string;
  recommendationScore: number;
  transcript: string;
  transcriptSource: string;
  transcriptUpdatedAt?: string;
  manuscript: string;
  url: string;
  publishedAt: string;
};

export type SocialVideoCollectionLog = {
  id: number;
  startedAt: string;
  finishedAt: string;
  discovered: number;
  hotMatched: number;
  scopeRejected: number;
  duplicateSkipped: number;
  created: number;
  status: string;
  message: string;
};

export type SocialCreator = {
  id: number;
  name: string;
  platform: SocialHotVideo["platform"];
  scope: SocialHotVideo["scope"];
  category: "高考升学" | "中考升学" | "常州本地教育" | "家庭教育规划";
  profileUrl: string;
  keywords: string[];
  enabled: boolean;
};

export type Material = {
  id: number;
  title: string;
  source: SourceType;
  sourceName?: string;
  taskId?: number;
  tags: string[];
  keywords?: string[];
  summary: string;
  content: string;
  status: "待整理" | "已入库";
};

export type SourceRecord = {
  id: number;
  name: string;
  type: SourceType;
  url: string;
  note: string;
  status: "启用" | "暂停";
};

export type CollectTask = {
  id: number;
  sourceId: number;
  sourceName: string;
  sourceType: SourceType;
  url: string;
  goal: string;
  status: "待采集" | "处理中" | "已完成";
  createdAt: string;
};

export type Draft = {
  id: number;
  type: DraftType;
  title: string;
  basedOn: string;
  status: "待审核" | "需修改" | "可发布";
  body: string;
};

export type OrganizedMaterial = {
  summary: string;
  tags: string[];
};

export type ImportedArticle = {
  title: string;
  content: string;
  source: SourceType;
  tags: string[];
  summary: string;
  mode?: string;
};

export type WorkspaceBackup = {
  version: 1;
  exportedAt: string;
  sources: SourceRecord[];
  tasks: CollectTask[];
  materials: Material[];
  drafts: Draft[];
};

export const storageKey = "education-content-platform-v1";

export const sourceTypes: SourceType[] = ["公众号", "视频号", "高校官网", "教育资讯", "手动资料"];

export const seedMaterials: Material[] = [
  {
    id: 1,
    title: "常州中考政策观察",
    source: "教育资讯",
    tags: ["常州教育", "中考", "政策"],
    summary: "围绕本地升学政策变化，整理家长最关心的时间线、录取规则和风险点。",
    content:
      "常州本地教育资讯需要持续跟踪政策发布、学校动态、招生计划、录取规则和家长关注的问题。",
    status: "已入库",
  },
  {
    id: 2,
    title: "行业大V表达风格样本",
    source: "公众号",
    tags: ["风格蒸馏", "行业观点"],
    summary: "观点先行，案例支撑，结尾给出行动建议，适合转化为公众号长文结构。",
    content:
      "该类文章通常用强观点开头，再拆解现象、原因和应对策略，语言直接但不夸张。",
    status: "已入库",
  },
  {
    id: 3,
    title: "高校基础资料卡片模板",
    source: "高校官网",
    tags: ["高校资料", "资料卡"],
    summary: "高校资料需要包含学校定位、优势专业、招生信息、就业方向和适合人群。",
    content:
      "高校资料库应保持结构稳定，方便后续生成对比、报考建议和专业文章。",
    status: "待整理",
  },
];

export const seedDrafts: Draft[] = [
  {
    id: 1,
    type: "公众号文章",
    title: "常州家长需要关注的三个升学变化",
    basedOn: "常州中考政策观察",
    status: "待审核",
    body: "开头提出家长痛点，再拆解政策变化、学校选择和时间规划，最后给出行动清单。",
  },
  {
    id: 2,
    type: "视频号脚本",
    title: "一分钟讲清常州升学信息怎么追",
    basedOn: "常州中考政策观察",
    status: "需修改",
    body: "口播结构：先说误区，再给三个信息来源，最后引导收藏和私信关键词。",
  },
];

export const seedSources: SourceRecord[] = [
  {
    id: 1,
    name: "常州教育资讯",
    type: "教育资讯",
    url: "https://example.com/changzhou-education",
    note: "本地政策、升学、学校动态",
    status: "启用",
  },
  {
    id: 2,
    name: "行业大V样本",
    type: "公众号",
    url: "https://mp.weixin.qq.com/",
    note: "用于风格蒸馏和观点结构分析",
    status: "启用",
  },
];

export const seedTasks: CollectTask[] = [
  {
    id: 1,
    sourceId: 1,
    sourceName: "常州教育资讯",
    sourceType: "教育资讯",
    url: "https://example.com/changzhou-education",
    goal: "收集本地政策、升学、学校动态",
    status: "待采集",
    createdAt: "演示任务",
  },
];

// 热门视频本地缓存样例：后端不可用时展示，也用于演示"抖音达标即推送"机制。
// 其中抖音且达阈值（isHot）的视频即为"已推送"对象。
export const seedSocialVideos: SocialHotVideo[] = [
  {
    id: 901,
    title: "2026 高考志愿填报：兴趣和热门专业到底怎么选？",
    creator: "每日甘肃",
    platform: "抖音",
    scope: "全国大博主",
    likes: 48200,
    saves: 9600,
    isHot: true,
    threshold: "抖音大博主：1250赞或500收藏",
    reason: "已命中推送阈值：48200赞、9600收藏，规则为抖音大博主：1250赞或500收藏。",
    recommendationScore: 71560,
    transcript: "",
    transcriptSource: "",
    manuscript:
      "高考志愿填报时，兴趣和热门专业常常打架。先说结论：热门会变冷，兴趣才走得远。\n\n第一步，把专业按“是否适合自己”和“就业基本面”两个维度拆开看。适合与否看你的学科优势、性格和长期坚持的意愿；就业基本面看行业周期、岗位需求和地域分布，而不是看当下哪个最火。\n\n第二步，别用“热门”替代“适合”。前几年大火的专业，四年后毕业时供需可能已经反转。真正稳的，是你能在这个领域里持续积累的能力。\n\n第三步，给兴趣一个落地通道。喜欢某个方向，就去找这个方向对应的专业组和院校层次，在分数允许范围内优先选“专业组内干净、不被调剂到完全不相关方向”的方案。\n\n一句话：用兴趣定方向，用数据定边界，用分数定院校。",
    url: "https://www.douyin.com/video/7656987460458581257",
    publishedAt: "2026-07-29 18:20",
  },
  {
    id: 902,
    title: "强基计划适合谁？一文讲清报考逻辑",
    creator: "藏视界",
    platform: "抖音",
    scope: "全国大博主",
    likes: 15300,
    saves: 2100,
    isHot: true,
    threshold: "抖音大博主：1250赞或500收藏",
    reason: "已命中推送阈值：15300赞、2100收藏，规则为抖音大博主：1250赞或500收藏。",
    recommendationScore: 23780,
    transcript: "",
    transcriptSource: "",
    manuscript:
      "强基计划适合两类学生：一类是学科竞赛有硬实力、目标基础学科的；一类是明确要走科研路线、愿意读研读博的。\n\n报考逻辑分三步。第一，看入围门槛：高考成绩要够，校测看重学科特长，竞赛奖项只是加分项不是入场券。第二，看专业锁定：强基一旦录取，原则上不能转专业，所以一定要确认自己真的喜欢这个基础学科。第三，看培养路径：本硕博衔接是强基的最大优势，但节奏快、压力大，要有长期投入的准备。\n\n不适合的人也很明显：只想借强基冲名校、对基础学科没兴趣的，进去后大概率痛苦。一句话，强基是给“真心想做研究”的人准备的通道。",
    url: "https://www.douyin.com/video/7655302630884822315",
    publishedAt: "2026-07-30 09:05",
  },
  {
    id: 903,
    title: "选专业别跟风：从就业和兴趣两个角度拆解",
    creator: "韩秀云讲经济",
    platform: "抖音",
    scope: "全国大博主",
    likes: 3200,
    saves: 880,
    isHot: true,
    threshold: "抖音大博主：1250赞或500收藏",
    reason: "已命中推送阈值：3200赞、880收藏，规则为抖音大博主：1250赞或500收藏。",
    recommendationScore: 9000,
    transcript: "",
    transcriptSource: "",
    url: "https://www.douyin.com/video/7655277710347947283",
    publishedAt: "2026-07-28 21:40",
  },
  {
    id: 904,
    title: "常州中考出分后，志愿怎么填不踩坑",
    creator: "龙城升学观察",
    platform: "抖音",
    scope: "常州本地",
    likes: 320,
    saves: 95,
    isHot: true,
    threshold: "常州范围抖音：125赞或50收藏",
    reason: "已命中推送阈值：320赞、95收藏，规则为常州范围抖音：125赞或50收藏。",
    recommendationScore: 3990,
    transcript: "",
    transcriptSource: "",
    url: "https://www.douyin.com/video/7655154629134683443",
    publishedAt: "2026-07-30 12:10",
  },
  {
    id: 905,
    title: "高考出分后家长最容易犯的 3 个错误",
    creator: "学考通教育科技",
    platform: "抖音",
    scope: "全国大博主",
    likes: 800,
    saves: 120,
    isHot: false,
    threshold: "抖音大博主：1250赞或500收藏",
    reason: "暂未达标：800赞、120收藏，规则为抖音大博主：1250赞或500收藏。",
    recommendationScore: 5200,
    transcript: "",
    transcriptSource: "",
    url: "https://www.douyin.com/video/7654879155032476991",
    publishedAt: "2026-07-30 08:00",
  },
  {
    id: 906,
    title: "志愿填报避坑指南（视频号版）",
    creator: "亦木老师",
    platform: "微信视频号",
    scope: "全国大博主",
    likes: 1200,
    saves: 300,
    isHot: true,
    threshold: "微信视频号大博主：250赞或50收藏",
    reason: "已命中推送阈值：1200赞、300收藏，规则为微信视频号大博主：250赞或50收藏。",
    recommendationScore: 6080,
    transcript: "",
    transcriptSource: "",
    url: "https://example.com/channels/video/7630685782566538496",
    publishedAt: "2026-07-29 15:30",
  },
];

export function buildWorkspaceBackup(input: Omit<WorkspaceBackup, "version" | "exportedAt">) {
  return {
    version: 1,
    exportedAt: new Date().toISOString(),
    ...input,
  } satisfies WorkspaceBackup;
}

export function parseWorkspaceBackup(text: string) {
  const data = JSON.parse(text) as Partial<WorkspaceBackup>;
  if (!Array.isArray(data.sources) || !Array.isArray(data.tasks)) return null;
  if (!Array.isArray(data.materials) || !Array.isArray(data.drafts)) return null;
  return {
    version: 1,
    exportedAt: data.exportedAt ?? new Date().toISOString(),
    sources: data.sources,
    tasks: data.tasks,
    materials: data.materials,
    drafts: data.drafts,
  } satisfies WorkspaceBackup;
}
