/* 知识全景的二维分类层。
 *
 * ── 为什么用标签，不用关键词猜 ────────────────────────────────
 * 245 篇里 244 篇有 tags（实测 364 个不同标签），还有 type 字段
 * （concept 79 / guide 43 / playbook 41 / principle 14 / pattern 13）。
 * 这些是作者在写这篇时亲手标下的分类意图，是第一手事实源。
 *
 * 之前那版拿正文关键词打分，是凭空造了第二套事实源 —— 两套规则迟早算出
 * 不同结果。实测后果："Codex 接管浏览器"因为正文里出现"网络"两个字，
 * 被判进网络层。关键词只在标签打不上分时兜底。
 *
 * ── 为什么是两个维度，而且是这两个 ────────────────────────────
 * 一维只能回答"哪一类少"，回答不了"哪个方向漏"。要看方向必须两个正交轴
 * 张成一个面 —— 面上的空格子才是洞。技能矩阵方法里叫"零覆盖缺口"：
 * 某一列全是 0，说明这个方向是真空。
 *
 *   X = 系统层次：问题出在哪一层（自底向上，排查顺序）
 *   Y = 知识类型：这一层上我懂的是哪种知识
 *
 * 两个轴正交的实证：`defect-analysis`（45 篇）只说明"这是故障模式"，
 * 不说明层次 —— 案例七讲兼容、案例三十一讲并发，层次不同。反过来
 * `database/mysql` 只说明层次，不说明是原理还是故障。
 *
 * ── 之前那版错在哪（别改回去）────────────────────────────────
 * 把"应用与架构"和"工程与人"放同一根轴上。前者是系统的一个层次，后者是
 * 工程活动的类型，是两种性质的东西。混在一根轴上这根轴就解释不清，只能靠
 * "八层"这个数字硬撑。现在没有"工程与人"这个层次 —— 它是活动不是层次。
 *
 * 打分规则只有这一份，scripts/ 下的审计脚本共用。改规则改这里。
 */
(function (global) {
  "use strict";

  /* ── X 轴：系统层次 ────────────────────────────────────────────
   * 从硬件往上到应用，工程师自底向上排查的顺序。
   * 判据：能排出上下顺序的才是层次。AI 是领域（横跨数据与应用），
   * 缺陷分析是类型（横跨所有层次），都不在 X 轴上。 */
  var LAYERS = [
    {
      id: "hw", name: "硬件与机器", name_en: "Hardware & machines", hint: "CPU / 内存 / 磁盘 / 网卡", hint_en: "CPU / memory / disk / NIC",
      tags: ["hardware", "gpu/performance", "performance/cpu", "performance/gpu",
             "performance/storage", "systems/memory", "memory", "resource-capacity",
             /* ai/training 跑在 GPU 上，算力与显存是这一层的约束 */
             "ai/training", "ai/inference", "ai/scheduling", "ai/capacity", "ai/moe"]
    },
    {
      id: "os", name: "操作系统与运行时", name_en: "OS & runtime", hint: "进程 / 线程 / 内存 / 文件", hint_en: "processes / threads / memory / files",
      tags: ["operating-systems/process", "operating-systems/fd", "operating-systems/locking",
             "systems/os", "systems/runtime", "systems/filesystems", "linux", "linux/shell",
             "linux/io", "linux/operations", "linux/metrics", "gc", "processes", "runtime",
             "memory-model", "python/runtime", "software/runtime", "concurrency",
             "backend/concurrency", "python/concurrency"]
    },
    {
      id: "net", name: "网络与通信", name_en: "Networking", hint: "TCP / HTTP / DNS / RPC", hint_en: "TCP / HTTP / DNS / RPC",
      tags: ["networking", "tcp", "systems/network", "performance/network",
             "backend/networking", "web/http", "web/browser", "routing",
             "distributed/communication", "distributed/load-balancing", "backend/service-mesh"]
    },
    {
      id: "data", name: "数据与存储", name_en: "Data & storage", hint: "索引 / 事务 / 一致性 / 缓存", hint_en: "indexes / transactions / consistency / caching",
      /* database* 与 data* 都算：实测两个前缀并存（database/mysql 8 篇、
         databases 6 篇、data/pipelines 2 篇），是同一层，没必要强行统一。 */
      tags: ["database", "databases", "database/mysql", "database/sqlite", "database/index",
             "database/query-optimization", "database/query-execution", "database/transaction",
             "database/transactions", "database/concurrency", "database/reliability",
             "database/ha", "database/operations", "database/capacity", "database/benchmark",
             "backend/database/sharding", "data", "data/storage", "data/sql", "data/nosql",
             "data/consistency", "data/modeling", "data/streaming", "data/orchestration",
             "data/pipelines", "data/reliability", "data/governance", "data/quality",
             "data/systems", "data/analytics", "data/cdc", "data-loss", "sql", "query",
             "redis", "clickhouse", "pulsar", "postgresql", "lsm", "columnar", "olap",
             "sharding", "backend/cache", "backend/transactions", "lineage", "backup",
             /* 检索与向量库本质在这一层：RAG 的下半身是索引，不是模型 */
             "ai/rag", "information-retrieval", "retrieval", "vector-search",
             "search", "knowledge-graph", "agent-engineering/rag",
             "agent-engineering/retrieval", "agent-engineering/agentic-retrieval",
             "agent-engineering/memory", "ai/embeddings", "ai/data",
             "agent/caching", "agent/conversation", "agent/context"]
    },
    {
      id: "dist", name: "分布式与协调", name_en: "Distributed systems & coordination", hint: "共识 / 复制 / 编排 / 可观测", hint_en: "consensus / replication / orchestration / observability",
      tags: ["distributed-systems", "distributed-systems/consistency",
             "distributed-systems/consensus", "distributed-systems/replication",
             "distributed-systems/time", "distributed/systems", "distributed/architecture",
             "kubernetes", "cloud-native", "infrastructure/containers", "infrastructure/selection",
             "messaging", "events", "ordering", "streaming", "consistency", "observability",
             "backend/observability", "performance/observability", "ai/observability",
             "agent-engineering/observability", "backend/infrastructure", "multi-tenancy",
             "backend/scalability", "backend/queues", "capacity", "overload", "resilience",
             /* 推理服务是分布式系统：调度、批处理、副本、队列 */
             "ai/serving", "ai/platform", "ai/operations", "ai/mlops", "ai/distributed",
             "ai/systems", "ai/runtime", "ai/architecture", "ai/observability",
             "ai/reliability", "ai/release", "agent-engineering/runtime",
             "agent-engineering/operations", "agent-engineering/state",
             "agent/optimization", "agent/multi-agent", "agent-engineering/frameworks",
             "ai/frameworks", "ai/tools", "ai/mcp", "agent-engineering/mcp",
             "agent-engineering/a2a"]
    },
    {
      id: "app", name: "应用与架构", name_en: "Applications & architecture", hint: "架构 / 设计 / 抽象 / 交付", hint_en: "architecture / design / abstraction / delivery",
      tags: ["architecture", "architecture/selection", "software/architecture",
             "backend/architecture", "engineering/architecture", "backend/design-patterns",
             "backend/design-patterns/state-machine", "backend/design-patterns/strategy",
             "backend/design-patterns/decorator", "backend/design-patterns/observer",
             "backend/design-patterns/adapter", "backend/design-reasoning",
             "backend/dependency-injection", "backend/dependency-inversion",
             "backend/domain-modeling", "backend/ddd", "backend/middleware",
             "backend/event-driven", "backend/legacy", "backend/migration", "backend/refactoring",
             "backend/api", "backend/acl", "backend/integration", "backend/writing",
             "backend/feature-flags", "backend/config", "backend/deployment", "api",
             "software/modularity", "software/compiler", "software/ast", "software/ci-cd",
             "software/version-control", "software/automation", "software/dependencies",
             "software/algorithms", "software/scheduling", "code-quality", "migrations",
             "data-structures", "algorithms/heap", "design", "frontend", "web", "typescript",
             "nodejs", "go", "java", "spring", "python/database",
             /* Agent 工程是应用层：编排、工具、控制流、上下文都是应用架构问题 */
             "agent-engineering/architecture", "agent-engineering/control-flow",
             "agent-engineering/overview", "agent-engineering/tools",
             "agent-engineering/prompting", "agent-engineering/context",
             "agent-engineering/sandbox", "agent-engineering/models",
             "agent-engineering/correctness", "agent-engineering/evaluation",
             "agent-engineering/testing", "agent/planning", "agent/task-decomposition",
             "agent/architecture", "agent/reflection", "agent/human-in-the-loop",
             "agent/prompt", "agent-skills", "agent-engineering", "agent",
             "ai/agents", "ai/coding-agents", "ai/coding", "ai/code-intelligence",
             "ai/agent", "ai/models", "ai/fundamentals", "ai/long-context",
             "ai/alignment", "ai/multimodal", "ai/generation", "ai/adaptation",
             "ai/knowledge-engineering", "ai/learning", "ai/evaluation", "ai-evals",
             "deep-learning", "ai-systems", "agent/reliability", "agent/safety"]
    }
  ];

  /* ── Y 轴：知识类型 ────────────────────────────────────────────
   * 同一层上可以有的五种知识。排查时顺着这条链走：
   * 先懂机制 → 才能观测 → 才能认出故障模式 → 才知道怎么修 → 最后沉淀成规矩。
   *
   * 按 list 顺序匹配，命中即停：一篇同时带 defect-analysis 和 concept 时，
   * 它是故障案例不是原理，所以 fail 排在 mech 前面。 */
  var KINDS = [
    {
      id: "fail", name: "故障模式", name_en: "Failure modes", hint: "它会怎么坏", hint_en: "how it breaks",
      tags: ["defect-analysis", "data-loss", "data/reliability", "correctness",
             "prompt-injection", "reliability/root-cause", "diagnosis"],
      types: ["case"]
    },
    {
      id: "obs", name: "观测诊断", name_en: "Observation & diagnosis", hint: "怎么看见、怎么定位", hint_en: "how to see it, how to pin it down",
      tags: ["observability", "performance/profiling", "performance/benchmark",
             "performance/observability", "linux/metrics", "testing/chaos",
             "research/verification", "software/static-analysis", "software/debugging",
             "ai/observability", "agent-engineering/observability", "monitoring"],
      types: ["reference", "audit", "radar"]
    },
    {
      id: "fix", name: "修复与规避", name_en: "Fixes & avoidance", hint: "坏了怎么办、怎么防", hint_en: "what to do when it breaks, how to prevent it",
      tags: ["resilience", "disaster-recovery", "backup", "reliability/lifecycle",
             "reliability/lease", "reliability/health-check", "security", "security/web",
             "security/operations", "backend/security", "agent-engineering/security",
             "ai/security", "ai/safety", "agent/safety", "agent/error-handling",
             "authorization", "identity", "supply-chain", "ai/supply-chain",
             "compatibility", "upstream-tracking", "backport"],
      types: ["decision", "pattern"]
    },
    {
      id: "prac", name: "工程实践", name_en: "Engineering practice", hint: "日常怎么做、守什么规矩", hint_en: "the daily routine and the rules to keep",
      tags: ["engineering/evidence", "ai/mlops", "ai/operations", "ai/release",
             "ai/governance", "ai/platform", "ai/engineering", "delivery", "workflow",
             "software/testing", "backend/testing", "testing", "quality",
             "operations", "operations/process", "reproducibility", "ai/reproducibility",
             "research/gaps", "research/freshness", "source/case-study", "source/index"],
      types: ["playbook", "guide", "note", "worklog", "project", "index"]
    },
    {
      id: "mech", name: "机制原理", name_en: "Mechanisms", hint: "它到底是怎么工作的", hint_en: "how it actually works",
      tags: ["ai/fundamentals", "ai/models", "ai/training", "ai/scaling", "ai/moe",
             "ai/alignment", "ai/multimodal", "deep-learning", "memory-model",
             "knowledge-graph", "vector-search", "information-retrieval", "retrieval",
             "systems", "methodology", "learning"],
      types: ["concept", "principle", "research", "overview", "map", "comparison",
              "evolution", "design", "architecture", "paper", "paper-analysis", "mechanism"]
    },
    {
      id: "vocab", name: "词汇与词源", name_en: "Vocabulary & etymology", hint: "名字从哪来、怎么记", hint_en: "where the names come from",
      tags: ["vocabulary", "terms/etymology"],
      types: ["reference", "overview", "map"]
    }
  ];

  /* 不进技术矩阵：元知识（讲知识库本身）与外部剪藏。
   * 混进来会让"数据与存储"这类格子凭空多出十几篇，缺口被填平。 */
  var EXCLUDE_PREFIX = ["meta/", "skill/", "research/paper"];
  var EXCLUDE_TAG = ["clippings"];
  var EXCLUDE_CATEGORY = ["Clippings", "知识库管理"];

  /* 关键词兜底：只在标签打不上分时启用 */
  var FALLBACK_LAYER = {
    hw: ["cpu","内存","磁盘","硬件","gpu","处理器","缓存行","访存"],
    os: ["进程","线程","协程","虚拟内存","文件系统","系统调用","内核","gc","垃圾回收","上下文切换","死锁"],
    net: ["tcp","http","dns","rpc","重传","丢包","socket","tls","quic","三次握手","抓包"],
    data: ["索引","事务","acid","数据库","sql","存储","缓存","redis","b+树","mvcc","慢查询"],
    dist: ["分布式","共识","raft","paxos","幂等","熔断","限流","kubernetes","服务发现","链路追踪"],
    app: ["架构","设计模式","抽象","模块化","耦合","内聚","领域","ddd","重构","solid","技术债"]
  };

  function tagList(note) {
    return (note.tags || []).map(function (t) { return String(t).toLowerCase(); });
  }

  function isExcluded(note) {
    var tags = tagList(note);
    if (EXCLUDE_CATEGORY.indexOf(note.category || "") >= 0) return true;
    for (var i = 0; i < tags.length; i++) {
      if (EXCLUDE_TAG.indexOf(tags[i]) >= 0) return true;
      for (var j = 0; j < EXCLUDE_PREFIX.length; j++) {
        if (tags[i].indexOf(EXCLUDE_PREFIX[j]) === 0) return true;
      }
    }
    return false;
  }

  /* 标签命中算 3 分；标签缺失时用关键词兜底算 1 分 —— 兜底永远赢不过真标签 */
  function matchAxis(list, note) {
    var tags = tagList(note);
    var type = String(note.type || "").toLowerCase();
    var text = [note.title || "", note.search_text || ""].join(" ").toLowerCase();
    var best = null, bestS = 0;
    for (var i = 0; i < list.length; i++) {
      var s = 0;
      var tg = list[i].tags || [];
      for (var k = 0; k < tg.length; k++) {
        if (tags.indexOf(tg[k]) >= 0) s += 3;
      }
      var ty = list[i].types || [];
      if (ty.indexOf(type) >= 0) s += 3;
      if (s === 0 && list[i].id && FALLBACK_LAYER[list[i].id]) {
        var fw = FALLBACK_LAYER[list[i].id];
        for (var m = 0; m < fw.length; m++) {
          if (text.indexOf(fw[m]) >= 0) { s += 1; break; }
        }
      }
      if (s > bestS) { bestS = s; best = list[i]; }
    }
    return { item: best, score: bestS };
  }

  /* Y 轴按 KINDS 顺序优先：并列时取靠前的（fail 先于 mech）。
   * 2026-09-22 修：先全表扫 tags 再扫 types。tags 是作者显式声明的语义，
   * 必须优先于类型兜底——否则 obs 的 types:[reference] 会抢走带
   * vocabulary tag 的词源文章（vocab 排在 KINDS 末尾，永远轮不到）。 */
  function matchKind(note) {
    var tags = tagList(note);
    var type = String(note.type || "").toLowerCase();
    for (var i = 0; i < KINDS.length; i++) {
      var tg = KINDS[i].tags || [], k;
      for (k = 0; k < tg.length; k++) if (tags.indexOf(tg[k]) >= 0) return { item: KINDS[i], score: 3 };
    }
    for (var j = 0; j < KINDS.length; j++) {
      var ty = KINDS[j].types || [];
      for (var k2 = 0; k2 < ty.length; k2++) if (ty[k2] === type) return { item: KINDS[j], score: 3 };
    }
    return { item: KINDS[KINDS.length - 1], score: 0 };
  }

  function classify(note) {
    if (isExcluded(note)) {
      return { path: note.path, title: note.title, excluded: true,
               reason: (note.category || "") === "Clippings" ? "clippings" : "meta" };
    }
    var L = matchAxis(LAYERS, note);
    var K = matchKind(note);
    return {
      path: note.path, title: note.title,
      category: note.category, type: note.type,
      words: note.words || 0, tags: tagList(note),
      layer: L.item ? L.item.id : null, layerScore: L.score,
      kind: K.item ? K.item.id : null, kindScore: K.score,
      /* 标签打不上、靠关键词兜底落位的，标出来供人工复核 —— 这类格子
         的数字不该当成事实看。 */
      guessed: L.score < 3
    };
  }

  function classifyAll(notes) { return notes.map(classify); }

  function matrix(items) {
    var cells = {};
    LAYERS.forEach(function (l) {
      KINDS.forEach(function (k) {
        cells[l.id + "|" + k.id] = { layer: l.id, kind: k.id, n: 0, words: 0, items: [] };
      });
    });
    items.forEach(function (it) {
      if (it.excluded || !it.layer || !it.kind) return;
      var c = cells[it.layer + "|" + it.kind];
      if (!c) return;
      c.n++; c.words += it.words; c.items.push(it);
    });
    return cells;
  }

  global.TKMatrix = {
    LAYERS: LAYERS, KINDS: KINDS,
    isExcluded: isExcluded,
    classify: classify, classifyAll: classifyAll, matrix: matrix
  };
})(typeof window !== "undefined" ? window : (typeof global !== "undefined" ? global : this));
