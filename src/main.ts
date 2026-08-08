import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import {
  AudioLines,
  BadgeCheck,
  CircleDollarSign,
  Clapperboard,
  ClipboardCheck,
  createIcons,
  FilePenLine,
  Film,
  FolderCheck,
  FolderPlus,
  Image,
  Images,
  MonitorPlay,
  PanelsTopLeft,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Route,
  ScanLine,
  ScanSearch,
  Scissors,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Video,
  WalletCards,
  X,
} from "lucide";
import "./styles.css";

type JsonObject = Record<string, unknown>;

interface WorkerRuntime {
  status?: string;
  taskState?: string;
  stageStates?:
    | Record<string, string>
    | Array<{
        stageId?: string;
        outcome?: string;
        workers?: string[];
      }>;
}

interface VideoJob {
  jobId: string;
  source: string;
  merchantId: string;
  productionMode: "platform_independent";
  goal: string;
  media: string[];
  targetDurationSeconds: number;
  generationUnitPlan: {
    unitCount: number;
    units: Array<{ unitId: string; durationSeconds: number }>;
  };
  status: string;
  workbenchStatus: string;
  nextAllowedAction: string;
  runDir: string;
  appStatePath: string;
  professionalWorkerTeam?: WorkerRuntime;
  finalVideo?: string;
  updatedAt: string;
  writesExternalSystems: false;
}

interface JobList {
  count: number;
  jobs: VideoJob[];
  writesExternalSystems: false;
}

interface CreationDraft {
  merchantId: string;
  goal: string;
  productFeatures: string;
  coreSellingPoints: string;
  targetAudience: string;
  recommendedScene: string;
  contentType: string;
  shootingStyle: string;
  audioMode: string;
  supplement: string;
  referenceVideo: string;
  durationSeconds: number;
  candidateCount: number;
  selectedCandidateId: string;
}

interface AssetObservation {
  path: string;
  name: string;
  kind: "image" | "video";
  extension: string;
  sizeBytes: number;
  visualStatus: string;
}

interface MaterialAnalysis {
  status: string;
  mediaCount: number;
  assetObservations: AssetObservation[];
  insight: {
    productFeatures: string[];
    coreSellingPoints: string[];
    targetAudiences: string[];
    usageScenarios: string[];
    evidenceStatus: string;
  };
}

interface CreationBeat {
  label: string;
  time: string;
  intent: string;
}

interface CreativeCandidate {
  candidateId: string;
  status: string;
  strategy: string;
  contentType: string;
  shootingStyle: string;
  audioMode: string;
  beats: CreationBeat[];
  riskGate: string;
}

interface CreationBlueprint {
  status: string;
  candidates: CreativeCandidate[];
  selectedCandidateId: string;
  generationUnitPlan: VideoJob["generationUnitPlan"];
  scopeNote: string;
}

const merchantLabels: Record<string, string> = {
  xiaoyuanli: "小院里",
  zuotingyouyuan: "佐庭右院",
  muyi: "沐颐",
  tanwei: "探味",
};

const workerOrder = [
  ["producer_intake", "制片人", "ClipboardCheck"],
  ["material_evidence", "素材分析", "ScanSearch"],
  ["creative_direction", "创意导演", "Clapperboard"],
  ["screenwriter_contract", "编剧", "FilePenLine"],
  ["storyboard_contract", "分镜导演", "PanelsTopLeft"],
  ["audio_contract", "音频设计", "AudioLines"],
  ["editor_assembly", "剪辑合成", "Scissors"],
  ["independent_qa_acceptance", "独立质检", "BadgeCheck"],
] as const;

const workerIdToStage: Record<string, string> = {
  executive_producer_worker: "producer_intake",
  material_producer_worker: "material_evidence",
  creative_director_worker: "creative_direction",
  screenwriter_worker: "screenwriter_contract",
  storyboard_director_worker: "storyboard_contract",
  audio_director_worker: "audio_contract",
  video_editor_worker: "editor_assembly",
  qa_supervisor_worker: "independent_qa_acceptance",
};

const defaultDraft = (): CreationDraft => ({
  merchantId: "xiaoyuanli",
  goal: "",
  productFeatures: "",
  coreSellingPoints: "",
  targetAudience: "",
  recommendedScene: "",
  contentType: "人物剧情",
  shootingStyle: "电影感叙事",
  audioMode: "角色对白 + BGM",
  supplement: "",
  referenceVideo: "",
  durationSeconds: 30,
  candidateCount: 3,
  selectedCandidateId: "",
});

const state: {
  jobs: VideoJob[];
  selectedJobId: string | null;
  media: string[];
  busy: boolean;
  notice: string;
  doctorStatus: string;
  creationStep: 1 | 2 | 3 | 4;
  draft: CreationDraft;
  analysis: MaterialAnalysis | null;
  blueprint: CreationBlueprint | null;
} = {
  jobs: [],
  selectedJobId: null,
  media: [],
  busy: false,
  notice: "",
  doctorStatus: "环境未检查",
  creationStep: 1,
  draft: defaultDraft(),
  analysis: null,
  blueprint: null,
};

const applicationIcons = {
  AudioLines,
  BadgeCheck,
  CircleDollarSign,
  Clapperboard,
  ClipboardCheck,
  FilePenLine,
  Film,
  FolderCheck,
  FolderPlus,
  Image,
  Images,
  MonitorPlay,
  PanelsTopLeft,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Route,
  ScanLine,
  ScanSearch,
  Scissors,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Video,
  WalletCards,
  X,
};

async function command(args: string[]): Promise<JsonObject> {
  const response = await invoke<JsonObject>("video_studio_command", { args });
  if (response.status === "POLICY_BLOCKED" || response.status === "BLOCKED") {
    throw new Error(String(response.message || "任务被本地安全策略拦截"));
  }
  return response;
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function lines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function creationBrief(): JsonObject {
  return {
    goal: state.draft.goal,
    productFeatures: lines(state.draft.productFeatures),
    coreSellingPoints: lines(state.draft.coreSellingPoints),
    targetAudiences: lines(state.draft.targetAudience),
    usageScenarios: lines(state.draft.recommendedScene),
    contentType: state.draft.contentType,
    shootingStyle: state.draft.shootingStyle,
    audioMode: state.draft.audioMode,
    supplement: state.draft.supplement,
    referenceVideo: state.draft.referenceVideo,
    durationSeconds: state.draft.durationSeconds,
    candidateCount: state.draft.candidateCount,
    selectedCandidateId: state.draft.selectedCandidateId,
  };
}

function statusLabel(value: string): string {
  const labels: Record<string, string> = {
    ready: "可继续",
    running: "执行中",
    blocked: "待处理",
    PASS: "通过",
    ACTIVE: "进行中",
    IN_PROGRESS: "进行中",
    PENDING: "等待",
    CANDIDATE: "候选",
    BLOCKED: "阻塞",
    FAILED: "失败",
    COMPLETE: "完成",
  };
  return labels[value] || value || "等待";
}

function selectedJob(): VideoJob | undefined {
  return state.jobs.find((job) => job.jobId === state.selectedJobId);
}

function workerStageStates(runtime?: WorkerRuntime): Record<string, string> {
  const raw = runtime?.stageStates;
  if (!raw) return {};
  if (!Array.isArray(raw)) return raw;
  const result: Record<string, string> = {};
  const severity: Record<string, number> = {
    PASS: 1,
    COMPLETE: 1,
    CANDIDATE: 2,
    PENDING: 2,
    ACTIVE: 3,
    IN_PROGRESS: 3,
    BLOCKED: 4,
    FAILED: 5,
  };
  raw.forEach((stage) => {
    const outcome = stage.outcome || "PENDING";
    (stage.workers || []).forEach((workerId) => {
      const key = workerIdToStage[workerId];
      if (!key) return;
      const previous = result[key] || "PASS";
      if ((severity[outcome] || 2) >= (severity[previous] || 2)) {
        result[key] = outcome;
      }
    });
  });
  return result;
}

function render(): void {
  const app = document.querySelector<HTMLDivElement>("#app");
  if (!app) return;
  const job = selectedJob();
  app.innerHTML = `
    <div class="app-shell">
      <header class="topbar">
        <div class="brand-lockup">
          <span class="brand-mark"><i data-lucide="clapperboard"></i></span>
          <div>
            <strong>OmniOps Video Studio</strong>
            <span>AI 视频创作</span>
          </div>
        </div>
        <div class="task-navigation">
          ${state.jobs.length ? `
            <label class="job-select-wrap">
              <span>任务</span>
              <select id="job-selector">
                <option value="">新建视频</option>
                ${state.jobs.map((item) => `
                  <option value="${escapeHtml(item.jobId)}" ${item.jobId === state.selectedJobId ? "selected" : ""}>
                    ${escapeHtml(merchantLabels[item.merchantId] || item.merchantId)} · ${escapeHtml(item.goal.split("\n")[0].slice(0, 22))}
                  </option>
                `).join("")}
              </select>
            </label>
          ` : ""}
          <button class="text-button" id="new-job-button" title="新建视频任务">
            <i data-lucide="plus"></i><span>新建</span>
          </button>
          <span class="runtime-status"><span class="status-dot"></span>${escapeHtml(state.doctorStatus)}</span>
          <button class="icon-button" id="doctor-button" title="检查运行环境" ${state.busy ? "disabled" : ""}>
            <i data-lucide="stethoscope"></i>
          </button>
          <button class="icon-button" id="refresh-button" title="刷新本地任务" ${state.busy ? "disabled" : ""}>
            <i data-lucide="refresh-cw"></i>
          </button>
        </div>
      </header>

      <main class="workspace">
        ${job ? renderJobWorkspace(job) : renderCreateWorkspace()}
      </main>

      <footer class="statusbar">
        <span>${escapeHtml(state.notice || "素材、任务和成片仅保存在本地")}</span>
        <span><i data-lucide="shield-check"></i>外部平台写入已关闭</span>
      </footer>
    </div>
    ${renderPaidDialog(job)}
  `;
  bindEvents();
  createIcons({ icons: applicationIcons });
}

function renderCreationSteps(activeStep: number, complete = false): string {
  const stepClass = (step: number) => {
    if (complete || step < activeStep) return "complete";
    if (step === activeStep) return "active";
    return "";
  };
  return `
    <nav class="creation-steps" aria-label="视频创作步骤">
      <button type="button" class="creation-step ${stepClass(1)}" data-step="1">
        <span class="step-index">${complete || activeStep > 1 ? "✓" : "1"}</span>
        <span><strong>素材上传</strong><small>图片、视频与人物参考</small></span>
      </button>
      <button type="button" class="creation-step ${stepClass(2)}" data-step="2">
        <span class="step-index">${complete || activeStep > 2 ? "✓" : "2"}</span>
        <span><strong>素材洞察</strong><small>确认卖点、人群和场景</small></span>
      </button>
      <button type="button" class="creation-step ${stepClass(3)}" data-step="3">
        <span class="step-index">${complete || activeStep > 3 ? "✓" : "3"}</span>
        <span><strong>创意方案</strong><small>类型、拍法、参考和时长</small></span>
      </button>
      <button type="button" class="creation-step ${stepClass(4)}" data-step="4">
        <span class="step-index">${complete ? "✓" : "4"}</span>
        <span><strong>制作确认</strong><small>选择方向并提交 Worker</small></span>
      </button>
    </nav>
  `;
}

function renderCreateWorkspace(): string {
  return `
    <div class="creation-page">
      <aside class="wizard-rail">
        <div class="wizard-title">
          <span class="eyebrow">新建视频</span>
          <h1>创建一条 AI 视频</h1>
        </div>
        ${renderCreationSteps(state.creationStep)}
        <div class="local-boundary">
          <i data-lucide="shield-check"></i>
          <span>不区分平台和账号<br />只生成本地视频</span>
        </div>
      </aside>
      <section class="creation-stage">
        ${renderCreationStep()}
      </section>
    </div>
  `;
}

function renderCreationStep(): string {
  if (state.creationStep === 1) return renderMaterialStep();
  if (state.creationStep === 2) return renderAnalysisStep();
  if (state.creationStep === 3) return renderPlanStep();
  return renderScriptStep();
}

function renderStageHeader(eyebrow: string, title: string, description: string): string {
  return `
    <header class="stage-header">
      <span class="eyebrow">${escapeHtml(eyebrow)}</span>
      <h2>${escapeHtml(title)}</h2>
      <p>${escapeHtml(description)}</p>
    </header>
  `;
}

function renderMaterialStep(): string {
  return `
    ${renderStageHeader("第一步", "上传图片与视频素材", "先建立本地素材清单，再进入内容洞察。人物参考、门店、菜品和实拍片段均可混合上传。")}
    <div class="upload-zone" id="pick-media-button">
      <span class="upload-icon"><i data-lucide="folder-plus"></i></span>
      <strong>${state.media.length ? `已选择 ${state.media.length} 项素材` : "点击选择素材"}</strong>
      <span>支持 JPG、PNG、WEBP、MP4、MOV，允许多选</span>
      <button type="button" class="secondary-button">
        <i data-lucide="images"></i><span>${state.media.length ? "继续添加" : "选择文件"}</span>
      </button>
    </div>
    ${state.media.length ? `
      <div class="asset-grid">
        ${state.media.map((path, index) => `
          <div class="asset-card">
            <div class="asset-preview">
              ${path.match(/\.(mp4|mov|m4v)$/i)
                ? `<video muted preload="metadata" src="${escapeHtml(convertFileSrc(path))}"></video><span><i data-lucide="video"></i></span>`
                : `<img src="${escapeHtml(convertFileSrc(path))}" alt="" />`}
            </div>
            <span class="asset-name" title="${escapeHtml(path)}">${escapeHtml(path.split(/[\\/]/).pop())}</span>
            <button type="button" class="icon-button remove-media" data-media-index="${index}" title="移除素材">
              <i data-lucide="x"></i>
            </button>
          </div>
        `).join("")}
      </div>
    ` : ""}
    <label class="field-row compact-field">
      <span>内容项目</span>
      <select id="merchant-id">
        ${Object.entries(merchantLabels).map(([value, label]) => `
          <option value="${value}" ${value === state.draft.merchantId ? "selected" : ""}>${label}</option>
        `).join("")}
      </select>
    </label>
    ${renderWizardActions(false, "开始内容分析")}
  `;
}

function renderAnalysisStep(): string {
  const observations = state.analysis?.assetObservations || [];
  return `
    ${renderStageHeader("第二步", "确认素材洞察", "将商户事实和创作假设分开整理，后续由素材 Worker 逐项核验画面证据。")}
    <div class="analysis-notice">
      <i data-lucide="scan-search"></i>
      <div><strong>${observations.length} 项本地素材已接收</strong><span>当前不上传素材、不虚构画面事实；语义内容将在正式 Worker 流程中独立核验。</span></div>
    </div>
    <div class="observation-strip">
      ${observations.map((asset) => `
        <div class="observation-item">
          <span class="asset-kind"><i data-lucide="${asset.kind === "video" ? "video" : "image"}"></i></span>
          <span><strong>${escapeHtml(asset.name)}</strong><small>${escapeHtml(asset.extension.toUpperCase())} · ${formatBytes(asset.sizeBytes)}</small></span>
          <em>待语义核验</em>
        </div>
      `).join("")}
    </div>
    <div class="analysis-grid">
      <label class="field-row wide">
        <span>创作目标</span>
        <textarea id="goal" maxlength="4000" placeholder="例如：以胜哥为主角，创作有冲突、有反转的餐饮剧情短片">${escapeHtml(state.draft.goal)}</textarea>
      </label>
      <label class="field-row">
        <span>产品 / 人物特性</span>
        <textarea id="product-features" placeholder="每行一项，例如：胜哥沉稳直接、牛杂分量足">${escapeHtml(state.draft.productFeatures)}</textarea>
      </label>
      <label class="field-row">
        <span>核心卖点</span>
        <textarea id="core-selling-points" placeholder="每行一项，例如：真实人物 IP、现场烟火气">${escapeHtml(state.draft.coreSellingPoints)}</textarea>
      </label>
      <label class="field-row">
        <span>目标人群</span>
        <textarea id="target-audience" placeholder="每行一项，例如：本地年轻人、朋友聚餐、新客">${escapeHtml(state.draft.targetAudience)}</textarea>
      </label>
      <label class="field-row">
        <span>使用场景</span>
        <textarea id="recommended-scene" placeholder="每行一项，例如：朋友聚餐、夜宵、到店点菜">${escapeHtml(state.draft.recommendedScene)}</textarea>
      </label>
    </div>
    ${renderWizardActions(true, "配置创意方案")}
  `;
}

function renderChoiceGroup(
  legend: string,
  name: keyof Pick<CreationDraft, "contentType" | "shootingStyle" | "audioMode">,
  choices: Array<[string, string]>,
): string {
  const selected = state.draft[name];
  return `
    <fieldset class="choice-group">
      <legend>${escapeHtml(legend)}</legend>
      <div class="choice-options">
        ${choices.map(([value, detail]) => `
          <label class="choice-option">
            <input type="radio" name="${name}" value="${escapeHtml(value)}" ${selected === value ? "checked" : ""} />
            <span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(detail)}</small></span>
          </label>
        `).join("")}
      </div>
    </fieldset>
  `;
}

function renderPlanStep(): string {
  return `
    ${renderStageHeader("第三步", "配置创意方案", "视频方案与创作脚本按成片目标编写，视频模型只负责 15 秒内的镜头单元，最后由剪辑与 QA Worker 合成验收。")}
    ${renderChoiceGroup("内容类型", "contentType", [
      ["人物剧情", "IP 角色、冲突和反转"],
      ["同城种草", "消费场景和到店理由"],
      ["菜品创意", "食物动作与视觉爆点"],
      ["品牌故事", "人物经历与门店价值"],
    ])}
    ${renderChoiceGroup("拍摄方式", "shootingStyle", [
      ["电影感叙事", "镜头语言和情绪推进"],
      ["Vlog 生活记录", "自然、真实、近距离"],
      ["快节奏反转", "短镜头、强钩子、密集信息"],
      ["真实素材混剪", "优先使用商户实拍证据"],
    ])}
    ${renderChoiceGroup("声音方案", "audioMode", [
      ["角色对白 + BGM", "适合人物剧情和中文口型"],
      ["旁白 + BGM", "适合种草与品牌故事"],
      ["现场感 + 音效", "突出动作和空间真实感"],
    ])}
    <div class="plan-options">
      <div class="reference-field">
        <span>复刻参考视频 <small>可选，仅学习结构与节奏</small></span>
        <div class="reference-picker">
          <button type="button" class="secondary-button" id="pick-reference-video">
            <i data-lucide="video"></i><span>${state.draft.referenceVideo ? "更换参考" : "选择视频"}</span>
          </button>
          <span title="${escapeHtml(state.draft.referenceVideo)}">${state.draft.referenceVideo ? escapeHtml(state.draft.referenceVideo.split(/[\\/]/).pop()) : "未选择"}</span>
          ${state.draft.referenceVideo ? `<button type="button" class="icon-button" id="clear-reference-video" title="移除参考"><i data-lucide="x"></i></button>` : ""}
        </div>
      </div>
      <label class="field-row supplement-field">
        <span>补充说明</span>
        <textarea id="supplement" placeholder="开场风格、广告感限制、必须保留的动作或结尾要求">${escapeHtml(state.draft.supplement)}</textarea>
      </label>
      <label class="candidate-count-field">
        <span>创意方向数量</span>
        <select id="candidate-count">
          ${[1, 2, 3, 4].map((count) => `<option value="${count}" ${state.draft.candidateCount === count ? "selected" : ""}>${count} 个</option>`).join("")}
        </select>
      </label>
      <label class="duration-field">
        <span>成片时长 <output id="duration-output">${state.draft.durationSeconds} 秒</output></span>
        <input id="duration-seconds" type="range" min="15" max="60" step="1" value="${state.draft.durationSeconds}" />
        <span class="duration-scale"><small>15 秒</small><small>30 秒</small><small>45 秒</small><small>60 秒</small></span>
      </label>
    </div>
    ${renderWizardActions(true, "生成创意方向")}
  `;
}

function renderScriptStep(): string {
  const candidates = state.blueprint?.candidates || [];
  const selectedId = state.draft.selectedCandidateId || state.blueprint?.selectedCandidateId;
  const selected = candidates.find((candidate) => candidate.candidateId === selectedId) || candidates[0];
  const units = state.blueprint?.generationUnitPlan?.units || [];
  return `
    ${renderStageHeader("第四步", "选择创意方向", "以下是付费生成前的本地候选。选中的方向会交给导演、编剧和分镜 Worker 重写，不会直接当作最终脚本。")}
    <div class="candidate-layout">
      <div class="candidate-list" aria-label="创意方向候选">
        <span class="section-label">创意方向候选</span>
        ${candidates.map((candidate, index) => `
          <label class="candidate-card ${candidate.candidateId === selected?.candidateId ? "selected" : ""}">
            <input type="radio" name="creativeCandidate" value="${escapeHtml(candidate.candidateId)}" ${candidate.candidateId === selected?.candidateId ? "checked" : ""} />
            <span class="candidate-index">${String(index + 1).padStart(2, "0")}</span>
            <span><strong>${escapeHtml(candidate.strategy)}</strong><small>${escapeHtml(candidate.beats[0]?.intent || "")}</small></span>
          </label>
        `).join("")}
      </div>
      <div class="script-overview">
        <div class="script-meta">
          <span>${escapeHtml(selected?.contentType || state.draft.contentType)}</span>
          <span>${escapeHtml(selected?.shootingStyle || state.draft.shootingStyle)}</span>
          <span>${escapeHtml(selected?.audioMode || state.draft.audioMode)}</span>
          <span>${state.draft.durationSeconds} 秒 · 9:16</span>
        </div>
        <ol class="script-beats">
          ${(selected?.beats || []).map((beat) => `
            <li><span>${escapeHtml(beat.time)}</span><div><strong>${escapeHtml(beat.label)}</strong><p>${escapeHtml(beat.intent)}</p></div></li>
          `).join("")}
        </ol>
      </div>
    </div>
    <div class="unit-plan">
      <span><strong>${units.length} 个生成单元</strong><small>逐镜头生成、提取实际尾帧、独立 QA 后合成</small></span>
      <div>${units.map((unit) => `<span>${unit.durationSeconds}s</span>`).join("")}</div>
    </div>
    <div class="production-summary">
      <span><i data-lucide="route"></i>最长 60 秒，自动拆分生成并合成</span>
      <span><i data-lucide="shield-check"></i>成片必须通过独立音画 QA</span>
      <span><i data-lucide="folder-check"></i>仅写入本地任务与报告</span>
    </div>
    <div class="wizard-actions">
      <button class="secondary-button" type="button" id="wizard-back">
        <i data-lucide="rotate-ccw"></i><span>返回修改</span>
      </button>
      <button class="primary-button prominent" type="button" id="create-video-button" ${state.busy ? "disabled" : ""}>
        <i data-lucide="sparkles"></i><span>交给专业团队创作</span>
      </button>
    </div>
  `;
}

function renderWizardActions(showBack: boolean, nextLabel: string): string {
  return `
    <div class="wizard-actions">
      ${showBack ? `
        <button class="secondary-button" type="button" id="wizard-back">
          <i data-lucide="rotate-ccw"></i><span>上一步</span>
        </button>
      ` : "<span></span>"}
      <button class="primary-button" type="button" id="wizard-next">
        <span>${escapeHtml(nextLabel)}</span><i data-lucide="play"></i>
      </button>
    </div>
  `;
}

function renderJobWorkspace(job: VideoJob): string {
  const stages = workerStageStates(job.professionalWorkerTeam);
  const units = job.generationUnitPlan?.units?.map((unit) => unit.durationSeconds).join(" + ") || "待编译";
  return `
    <div class="result-page">
      <aside class="wizard-rail result-rail">
        <div class="wizard-title">
          <span class="eyebrow">本地任务</span>
          <h1>${escapeHtml(merchantLabels[job.merchantId] || job.merchantId)}</h1>
        </div>
        ${renderCreationSteps(4, true)}
        <button class="secondary-button full-width" id="job-refresh-button" ${state.busy ? "disabled" : ""}>
          <i data-lucide="refresh-cw"></i><span>更新任务进度</span>
        </button>
      </aside>

      <section class="result-stage">
        <header class="result-header">
          <div>
            <span class="eyebrow">创作与验收</span>
            <h2>${escapeHtml(job.goal.split("\n")[0])}</h2>
          </div>
          <span class="state-pill ${escapeHtml(job.status)}">${escapeHtml(statusLabel(job.status))}</span>
        </header>

        <div class="result-primary">
          <div class="preview-surface">
            ${job.finalVideo ? `
              <video class="video-preview" controls src="${escapeHtml(convertFileSrc(job.finalVideo))}"></video>
            ` : `
              <div class="preview-empty">
                <span class="preview-icon"><i data-lucide="monitor-play"></i></span>
                <strong>专业团队正在制作</strong>
                <span>成片通过独立 QA 后显示在这里</span>
              </div>
            `}
          </div>
          <div class="task-summary">
            <span class="eyebrow">当前阶段</span>
            <strong>${escapeHtml(job.nextAllowedAction || "读取任务状态")}</strong>
            <dl>
              <div><dt>成片</dt><dd>${job.targetDurationSeconds} 秒 · 9:16</dd></div>
              <div><dt>生成单元</dt><dd>${escapeHtml(units)} 秒</dd></div>
              <div><dt>素材</dt><dd>${job.media.length} 项</dd></div>
              <div><dt>来源</dt><dd>${job.source === "weixin" ? "微信 CODEX" : "桌面端"}</dd></div>
            </dl>
            <button class="primary-button full-width" id="next-button" ${state.busy ? "disabled" : ""}>
              <i data-lucide="route"></i><span>读取下一步</span>
            </button>
          </div>
        </div>

        <details class="professional-details">
          <summary>
            <span><i data-lucide="clapperboard"></i><strong>专业 Worker 制作详情</strong></span>
            <small>导演、编剧、分镜、素材、音频、剪辑与独立质检</small>
          </summary>
          <div class="professional-content">
            <div class="worker-track">
              ${workerOrder.map(([key, label, icon]) => {
                const status = stages[key] || "PENDING";
                return `
                  <div class="worker-node ${escapeHtml(status.toLowerCase())}">
                    <span class="worker-icon"><i data-lucide="${icon}"></i></span>
                    <strong>${label}</strong>
                    <small>${escapeHtml(statusLabel(status))}</small>
                  </div>
                `;
              }).join("")}
            </div>
            <div class="professional-grid">
              <section>
                <span class="eyebrow">本地证据</span>
                <dl class="evidence-list">
                  <div><dt>任务编号</dt><dd>${escapeHtml(job.jobId)}</dd></div>
                  <div><dt>工作台</dt><dd>${escapeHtml(statusLabel(job.workbenchStatus))}</dd></div>
                  <div><dt>运行目录</dt><dd title="${escapeHtml(job.runDir)}">${escapeHtml(job.runDir || "等待创建")}</dd></div>
                </dl>
              </section>
              <section>
                <span class="eyebrow">专业操作</span>
                <div class="action-buttons">
                  <button class="secondary-button" id="preflight-button" ${state.busy ? "disabled" : ""}>
                    <i data-lucide="scan-line"></i><span>运行预检</span>
                  </button>
                  <button class="secondary-button" id="acceptance-button" ${state.busy ? "disabled" : ""}>
                    <i data-lucide="badge-check"></i><span>运行验收</span>
                  </button>
                  <button class="primary-button" id="open-paid-dialog" ${state.busy ? "disabled" : ""}>
                    <i data-lucide="sparkles"></i><span>生成下一镜头</span>
                  </button>
                </div>
              </section>
            </div>
          </div>
        </details>
      </section>
    </div>
  `;
}

function renderPaidDialog(job?: VideoJob): string {
  if (!job) return "";
  return `
    <dialog id="paid-dialog">
      <form method="dialog" class="paid-dialog-content">
        <div class="dialog-heading">
          <span class="dialog-icon"><i data-lucide="wallet-cards"></i></span>
          <div>
            <span class="eyebrow">一次性付费授权</span>
            <h2>生成下一镜头</h2>
          </div>
          <button class="icon-button" value="cancel" title="关闭"><i data-lucide="x"></i></button>
        </div>
        <label class="field-row">
          <span>授权编号</span>
          <input id="paid-authorization-id" required minlength="6" placeholder="例如 paid-20260724-shot-01" />
        </label>
        <div class="dialog-facts">
          <span><i data-lucide="circle-dollar-sign"></i>仅授权一个付费镜头</span>
          <span><i data-lucide="rotate-ccw"></i>失败后不会自动重试</span>
          <span><i data-lucide="shield-check"></i>授权编号不可重复使用</span>
        </div>
        <div class="dialog-actions">
          <button class="secondary-button" value="cancel">取消</button>
          <button class="primary-button" type="button" id="confirm-paid-generation">
            <i data-lucide="play"></i><span>确认并生成</span>
          </button>
        </div>
      </form>
    </dialog>
  `;
}

function persistDraft(): void {
  const merchant = document.querySelector<HTMLSelectElement>("#merchant-id");
  const goal = document.querySelector<HTMLTextAreaElement>("#goal");
  const productFeatures = document.querySelector<HTMLTextAreaElement>("#product-features");
  const coreSellingPoints = document.querySelector<HTMLTextAreaElement>("#core-selling-points");
  const targetAudience = document.querySelector<HTMLTextAreaElement>("#target-audience");
  const recommendedScene = document.querySelector<HTMLTextAreaElement>("#recommended-scene");
  const supplement = document.querySelector<HTMLTextAreaElement>("#supplement");
  const candidateCount = document.querySelector<HTMLSelectElement>("#candidate-count");
  const duration = document.querySelector<HTMLInputElement>("#duration-seconds");
  if (merchant) state.draft.merchantId = merchant.value;
  if (goal) state.draft.goal = goal.value.trim();
  if (productFeatures) state.draft.productFeatures = productFeatures.value.trim();
  if (coreSellingPoints) state.draft.coreSellingPoints = coreSellingPoints.value.trim();
  if (targetAudience) state.draft.targetAudience = targetAudience.value.trim();
  if (recommendedScene) state.draft.recommendedScene = recommendedScene.value.trim();
  if (supplement) state.draft.supplement = supplement.value.trim();
  if (candidateCount) state.draft.candidateCount = Number(candidateCount.value);
  if (duration) state.draft.durationSeconds = Number(duration.value);
  (["contentType", "shootingStyle", "audioMode"] as const).forEach((name) => {
    const checked = document.querySelector<HTMLInputElement>(`input[name="${name}"]:checked`);
    if (checked) state.draft[name] = checked.value;
  });
}

function resetCreation(): void {
  state.selectedJobId = null;
  state.creationStep = 1;
  state.media = [];
  state.draft = defaultDraft();
  state.analysis = null;
  state.blueprint = null;
  state.notice = "";
  render();
}

function goToCreationStep(step: number): void {
  persistDraft();
  if (step > 1 && state.media.length === 0) {
    state.notice = "请先上传至少一项图片或视频素材";
    state.creationStep = 1;
    render();
    return;
  }
  if (step > 1 && !state.analysis) {
    state.notice = "请先完成本地素材接收检查";
    state.creationStep = 1;
    render();
    return;
  }
  if (step > 2 && !state.draft.goal) {
    state.notice = "请先填写创作目标";
    state.creationStep = 2;
    render();
    return;
  }
  if (step > 3 && !state.blueprint) {
    state.notice = "请先生成创意方向";
    state.creationStep = 3;
    render();
    return;
  }
  state.creationStep = Math.max(1, Math.min(4, step)) as 1 | 2 | 3 | 4;
  state.notice = "";
  render();
}

function bindEvents(): void {
  document.querySelector("#doctor-button")?.addEventListener("click", runDoctor);
  document.querySelector("#refresh-button")?.addEventListener("click", loadJobs);
  document.querySelector("#new-job-button")?.addEventListener("click", resetCreation);
  document.querySelector<HTMLSelectElement>("#job-selector")?.addEventListener("change", (event) => {
    const value = (event.currentTarget as HTMLSelectElement).value;
    if (!value) {
      resetCreation();
      return;
    }
    state.selectedJobId = value;
    render();
  });
  document.querySelectorAll<HTMLElement>(".creation-step").forEach((element) => {
    element.addEventListener("click", () => {
      if (selectedJob()) return;
      goToCreationStep(Number(element.dataset.step));
    });
  });
  document.querySelector("#wizard-next")?.addEventListener("click", () => {
    if (state.creationStep === 1) {
      void analyzeMaterials();
      return;
    }
    if (state.creationStep === 3) {
      void compileBrief();
      return;
    }
    goToCreationStep(state.creationStep + 1);
  });
  document.querySelector("#wizard-back")?.addEventListener("click", () =>
    goToCreationStep(state.creationStep - 1),
  );
  document.querySelector("#create-video-button")?.addEventListener("click", submitJob);
  document.querySelector("#duration-seconds")?.addEventListener("input", (event) => {
    const value = (event.currentTarget as HTMLInputElement).value;
    const output = document.querySelector<HTMLOutputElement>("#duration-output");
    if (output) output.value = `${value} 秒`;
  });
  document.querySelector("#pick-media-button")?.addEventListener("click", pickMedia);
  document.querySelector("#pick-reference-video")?.addEventListener("click", pickReferenceVideo);
  document.querySelector("#clear-reference-video")?.addEventListener("click", () => {
    state.draft.referenceVideo = "";
    state.blueprint = null;
    render();
  });
  document.querySelectorAll<HTMLInputElement>('input[name="creativeCandidate"]').forEach((element) => {
    element.addEventListener("change", () => {
      state.draft.selectedCandidateId = element.value;
      render();
    });
  });
  document.querySelectorAll<HTMLElement>(".remove-media").forEach((element) => {
    element.addEventListener("click", (event) => {
      event.stopPropagation();
      state.media.splice(Number(element.dataset.mediaIndex), 1);
      state.analysis = null;
      state.blueprint = null;
      render();
    });
  });
  document.querySelector("#job-refresh-button")?.addEventListener("click", refreshJob);
  document.querySelector("#next-button")?.addEventListener("click", () => executeAction("next"));
  document.querySelector("#preflight-button")?.addEventListener("click", () =>
    executeAction("execute", ["--action", "run-step", "--step", "preflight"]),
  );
  document.querySelector("#acceptance-button")?.addEventListener("click", () =>
    executeAction("acceptance"),
  );
  document.querySelector("#open-paid-dialog")?.addEventListener("click", () => {
    document.querySelector<HTMLDialogElement>("#paid-dialog")?.showModal();
  });
  document.querySelector("#confirm-paid-generation")?.addEventListener("click", executePaidGeneration);
}

async function withBusy(operation: () => Promise<void>): Promise<void> {
  state.busy = true;
  render();
  try {
    await operation();
  } catch (error) {
    state.notice = error instanceof Error ? error.message : String(error);
  } finally {
    state.busy = false;
    render();
  }
}

async function loadJobs(): Promise<void> {
  await withBusy(async () => {
    const result = (await command(["list"])) as unknown as JobList;
    state.jobs = result.jobs;
    if (state.selectedJobId && !state.jobs.some((job) => job.jobId === state.selectedJobId)) {
      state.selectedJobId = null;
    }
    state.notice = `已同步 ${result.count} 个本地任务`;
  });
}

async function runDoctor(): Promise<void> {
  await withBusy(async () => {
    const result = await command(["doctor"]);
    state.doctorStatus = result.status === "PASS" ? "运行环境正常" : "运行环境需处理";
    state.notice = state.doctorStatus;
  });
}

async function pickMedia(): Promise<void> {
  const selection = await open({
    multiple: true,
    directory: false,
    filters: [
      {
        name: "图片与视频",
        extensions: ["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v"],
      },
    ],
  });
  if (!selection) return;
  state.media = Array.from(
    new Set([...state.media, ...(Array.isArray(selection) ? selection : [selection])]),
  );
  state.analysis = null;
  state.blueprint = null;
  state.notice = `已选择 ${state.media.length} 项素材`;
  render();
}

async function pickReferenceVideo(): Promise<void> {
  const selection = await open({
    multiple: false,
    directory: false,
    filters: [{ name: "参考视频", extensions: ["mp4", "mov", "m4v"] }],
  });
  if (!selection || Array.isArray(selection)) return;
  state.draft.referenceVideo = selection;
  state.blueprint = null;
  state.notice = "已加入复刻参考视频";
  render();
}

async function analyzeMaterials(): Promise<void> {
  persistDraft();
  if (!state.media.length) {
    goToCreationStep(2);
    return;
  }
  await withBusy(async () => {
    const args = ["analyze", "--merchant-id", state.draft.merchantId];
    state.media.forEach((path) => args.push("--media", path));
    state.analysis = (await command(["analyze", ...args.slice(1)])) as unknown as MaterialAnalysis;
    state.blueprint = null;
    state.creationStep = 2;
    state.notice = `已接收 ${state.analysis.mediaCount} 项本地素材，等待补充洞察`;
  });
}

async function compileBrief(): Promise<void> {
  persistDraft();
  if (!state.draft.goal) {
    goToCreationStep(3);
    return;
  }
  await withBusy(async () => {
    state.blueprint = (await command(["compile-brief", "--brief-json", JSON.stringify(
      creationBrief(),
    )])) as unknown as CreationBlueprint;
    state.draft.selectedCandidateId = state.blueprint.selectedCandidateId;
    state.creationStep = 4;
    state.notice = `已生成 ${state.blueprint.candidates.length} 个创意方向`;
  });
}

async function submitJob(): Promise<void> {
  persistDraft();
  const selectedCandidate = state.blueprint?.candidates.find(
    (candidate) => candidate.candidateId === state.draft.selectedCandidateId,
  );
  const brief = [
    state.draft.goal,
    `人物或产品特征：${state.draft.productFeatures || "由素材分析 Worker 提取"}`,
    `核心卖点：${state.draft.coreSellingPoints || "由创意导演从核验素材中提取"}`,
    `目标人群：${state.draft.targetAudience || "由内容分析 Worker生成候选"}`,
    `使用场景：${state.draft.recommendedScene || "由创意导演根据素材确定"}`,
    `视频类型：${state.draft.contentType}`,
    `拍摄方式：${state.draft.shootingStyle}`,
    `声音方案：${state.draft.audioMode}`,
    `选定创意方向：${selectedCandidate?.strategy || "由创意导演复核"}`,
  ].join("\n");
  await withBusy(async () => {
    const args = [
      "submit",
      "--merchant-id",
      state.draft.merchantId,
      "--goal",
      brief,
      "--duration-seconds",
      String(state.draft.durationSeconds),
      "--brief-json",
      JSON.stringify({
        ...creationBrief(),
        selectedCandidate,
        generationUnitPlan: state.blueprint?.generationUnitPlan,
      }),
      "--source",
      "desktop",
    ];
    state.media.forEach((path) => args.push("--media", path));
    const created = (await command(args)) as unknown as VideoJob;
    state.selectedJobId = created.jobId;
    state.media = [];
    state.creationStep = 1;
    state.draft = defaultDraft();
    state.analysis = null;
    state.blueprint = null;
    const listed = (await command(["list"])) as unknown as JobList;
    state.jobs = listed.jobs;
    state.notice = "视频任务已进入专业 Worker 流程";
  });
}

async function refreshJob(): Promise<void> {
  const job = selectedJob();
  if (!job) return;
  await withBusy(async () => {
    await command(["status", "--job-id", job.jobId, "--refresh"]);
    const listed = (await command(["list"])) as unknown as JobList;
    state.jobs = listed.jobs;
    state.notice = "Worker 状态已更新";
  });
}

async function executeAction(action: string, tail: string[] = []): Promise<void> {
  const job = selectedJob();
  if (!job) return;
  await withBusy(async () => {
    await command([action, "--job-id", job.jobId, ...tail]);
    const listed = (await command(["list"])) as unknown as JobList;
    state.jobs = listed.jobs;
    state.notice = action === "acceptance" ? "独立验收已完成" : "任务状态已更新";
  });
}

async function executePaidGeneration(): Promise<void> {
  const job = selectedJob();
  const input = document.querySelector<HTMLInputElement>("#paid-authorization-id");
  const authorizationId = input?.value.trim() || "";
  if (!job || authorizationId.length < 6) {
    input?.reportValidity();
    return;
  }
  document.querySelector<HTMLDialogElement>("#paid-dialog")?.close();
  await withBusy(async () => {
    await command([
      "execute",
      "--job-id",
      job.jobId,
      "--action",
      "run-step",
      "--step",
      "ai-video-sequential-executor-execute-next",
      "--paid-authorization-id",
      authorizationId,
    ]);
    const listed = (await command(["list"])) as unknown as JobList;
    state.jobs = listed.jobs;
    state.notice = "一个付费镜头任务已执行，等待哈希绑定 QA";
  });
}

render();
void loadJobs();
