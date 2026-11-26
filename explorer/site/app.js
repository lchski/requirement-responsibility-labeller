/* Policy requirements explorer (prototype).
 *
 * A single page, routed on the URL hash, over data/explorer.json (built by explorer/build.py).
 * Views: #/ (home), #/requirements?…filters, #/roles, #/role/<id>, #/instruments, #/instrument/<id>, #/about.
 * UI components come from the GC Design System (gcds-*), loaded in index.html.
 */
(function () {
  "use strict";

  const PAGE_SIZE = 100;
  const app = document.getElementById("app");
  let D = null; // the data, once loaded

  // ---------- helpers ----------

  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const attr = esc;
  const fmt = (n) => Number(n).toLocaleString("en-CA");
  const plural = (n, one, many) => `${fmt(n)} ${n === 1 ? one : many || one + "s"}`;

  function parseHash() {
    const raw = location.hash.replace(/^#/, "") || "/";
    const [path, query] = raw.split("?");
    const parts = path.split("/").filter(Boolean);
    return { view: parts[0] || "home", arg: parts[1], params: new URLSearchParams(query || "") };
  }

  function href(view, params) {
    const q = params ? new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null && v !== false)).toString() : "";
    return `#/${view}${q ? "?" + q : ""}`;
  }

  function tbsLink(inst, frag) {
    return frag ? `${inst.url}#${frag}` : inst.url;
  }

  function termsOf(q) {
    return (q || "").toLowerCase().split(/\s+/).filter((t) => t.length > 1);
  }

  function highlight(text, terms) {
    let out = esc(text);
    if (!terms.length) return out;
    const re = new RegExp("(" + terms.map((t) => esc(t).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")", "gi");
    return out.replace(re, "<mark>$1</mark>");
  }

  function setTitle(t) {
    document.title = `${t ? t + " – " : ""}Policy requirements explorer (prototype)`;
  }

  function setNav(view) {
    const map = { requirements: "requirements", role: "roles", roles: "roles", instrument: "instruments", instruments: "instruments", about: "about" };
    document.querySelectorAll("gcds-nav-link[data-nav]").forEach((el) => {
      if (el.dataset.nav === map[view]) el.setAttribute("current", "");
      else el.removeAttribute("current");
    });
  }

  function onValue(el, fn) {
    // gcds form components emit gcdsChange / gcdsInput; read the value off the element.
    const read = (e) => fn(e.detail !== undefined && typeof e.detail !== "object" ? e.detail : el.value, e);
    el.addEventListener("gcdsChange", read);
    el.addEventListener("gcdsInput", read);
  }

  function debounce(fn, ms) {
    let t;
    return (...a) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...a), ms);
    };
  }

  // ---------- data ----------

  async function load() {
    const res = await fetch("data/explorer.json");
    if (!res.ok) throw new Error(`data/explorer.json: HTTP ${res.status}`);
    const d = await res.json();
    const F = Object.fromEntries(d.itemFields.map((f, i) => [f, i]));
    d.items = d.items.map((a, i) => {
      const o = { i };
      for (const f in F) o[f] = a[F[f]];
      return o;
    });
    d.roleById = new Map(d.roles.map((r) => [r.id, r]));
    d.instById = new Map(d.instruments.map((x) => [x.id, x]));
    d.typeRank = Object.fromEntries(d.types.map((t, i) => [t, i]));
    // Instrument display order: by type (policies first), then title.
    const order = d.instruments
      .map((x, i) => i)
      .sort((a, b) => {
        const A = d.instruments[a], B = d.instruments[b];
        return (d.typeRank[A.type] - d.typeRank[B.type]) || A.title.localeCompare(B.title);
      });
    d.instRank = new Array(order.length);
    order.forEach((idx, rank) => (d.instRank[idx] = rank));
    // Subset roles, and how many instruments each role appears in.
    d.roles.forEach((r) => {
      r.children = d.roles.filter((c) => c.parent === r.id).map((c) => c.id);
      r.inst = new Set();
    });
    d.items.forEach((it) => {
      it.instObj = d.instruments[it.inst];
      it.search = [it.text, it.stem, it.topic, it.section, it.actor, it.qualifier, it.instObj.title].join(" \u0001 ").toLowerCase();
      if (it.role != null) d.roleById.get(it.role).inst.add(it.inst);
    });
    d.hasItemTypes = d.items.some((it) => it.itemType);
    return d;
  }

  function roleSet(roleParam, includeSubsets) {
    if (!roleParam) return null;
    if (roleParam === "none") return "none";
    const id = Number(roleParam);
    const set = new Set([id]);
    if (includeSubsets) {
      const walk = (rid) => (D.roleById.get(rid)?.children || []).forEach((c) => { set.add(c); walk(c); });
      walk(id);
    }
    return set;
  }

  function filterItems(f) {
    const terms = termsOf(f.q);
    const roles = roleSet(f.role, f.sub);
    const inst = f.inst ? Number(f.inst) : null;
    return D.items
      .filter((it) => {
        if (roles === "none" ? it.role != null : roles && !roles.has(it.role)) return false;
        if (inst && it.instObj.id !== inst) return false;
        if (f.type && it.instObj.type !== f.type) return false;
        if (f.mand && !it.instObj.mandatory) return false;
        if (f.mod && it.modality !== f.mod) return false;
        if (f.resp && it.itemType && it.itemType !== "responsibility") return false;
        for (const t of terms) if (!it.search.includes(t)) return false;
        return true;
      })
      .sort((a, b) => D.instRank[a.inst] - D.instRank[b.inst] || a.i - b.i);
  }

  // ---------- shared fragments ----------

  function roleLabel(r) {
    return r ? r.name : "No role identified";
  }

  function typeTag(inst) {
    return `<span class="tag tag--${inst.mandatory ? "mandatory" : "guidance"}" title="${inst.mandatory ? "Sets requirements" : "Guidance (advice, not requirements)"}">${esc(inst.type)}</span>`;
  }

  function itemHTML(it, opts) {
    const terms = opts.terms || [];
    const inst = it.instObj;
    const role = it.role != null ? D.roleById.get(it.role) : null;
    const where = [it.section, it.topic].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i);
    const meta = [];
    if (it.modality) meta.push(`<span class="tag tag--modality">${esc(it.modality)}</span>`);
    if (it.frequency) meta.push(`<span class="tag tag--frequency">${esc(it.frequency)}</span>`);

    let who;
    if (role) {
      const parent = role.parent ? D.roleById.get(role.parent) : null;
      who = `<a href="${href("role/" + role.id)}">${esc(role.name)}</a>`;
      if (it.qualifier) who += ` <span class="muted">(${highlight(it.qualifier, terms)})</span>`;
      if (parent) who += ` <span class="muted">· a subset of <a href="${href("role/" + parent.id)}">${esc(parent.name)}</a></span>`;
    } else if (it.actor) {
      who = `<span>${highlight(it.actor, terms)}</span> <span class="muted">(not matched to a role)</span>`;
    } else {
      who = `<span class="muted">Not identified</span>`;
    }
    const asWritten = role && it.actor && it.actor.toLowerCase() !== role.name.toLowerCase()
      ? `<div class="item__detail">As written: “${highlight(it.actor, terms)}”${it.actorHow === "ancestor" || it.actorHow === "appendix-reference" ? " (from the clause this item sits under)" : it.actorHow === "llm" ? " (suggested by a language model)" : ""}</div>`
      : "";
    const others = it.others ? `<div class="item__detail">Also involves: ${highlight(it.others, terms)}</div>` : "";
    const anchorText = /#/.test(it.anchor) ? "Go to section" : it.anchor;

    return `<li class="item" id="item-${it.i}">
      <div class="item__head">
        <a class="item__anchor" href="${attr(tbsLink(inst, it.frag))}" target="_blank" rel="noopener" title="Open this clause on the Treasury Board Secretariat website">${esc(anchorText)}<span class="sr-only"> (opens on tbs-sct.canada.ca)</span></a>
        ${where.length ? `<span class="item__where">${where.map((w) => highlight(w, terms)).join(" › ")}</span>` : ""}
      </div>
      ${it.stem ? `<p class="item__stem">${highlight(it.stem, terms)}</p>` : ""}
      <p class="item__text">${highlight(it.text, terms)}</p>
      <div class="item__meta">
        <span class="item__who"><span class="label">Responsible:</span> ${who}</span>
        ${meta.join(" ")}
      </div>
      ${asWritten}${others}
    </li>`;
  }

  function groupedByInstrument(items, opts) {
    let html = "";
    let cur = null;
    for (const it of items) {
      if (it.inst !== cur) {
        if (cur !== null) html += "</ol></section>";
        cur = it.inst;
        const inst = it.instObj;
        html += `<section class="inst-group">
          <h3 class="inst-group__title"><a href="${href("instrument/" + inst.id)}">${esc(inst.title)}</a> ${typeTag(inst)}</h3>
          <ol class="items">`;
      }
      html += itemHTML(it, opts);
    }
    if (cur !== null) html += "</ol></section>";
    return html;
  }

  function roleOptions(selected) {
    const sel = (v) => (String(v) === String(selected || "") ? " selected" : "");
    let html = `<option value=""${sel("")}>Any role</option>`;
    for (const g of D.groups) {
      const rs = D.roles.filter((r) => r.group === g && r.n > 0).sort((a, b) => a.name.localeCompare(b.name));
      if (!rs.length) continue;
      html += `<optgroup label="${attr(g)}">${rs.map((r) => `<option value="${r.id}"${sel(r.id)}>${esc(r.name)} (${fmt(r.n)})</option>`).join("")}</optgroup>`;
    }
    const none = D.items.filter((it) => it.role == null).length;
    html += `<optgroup label="Other"><option value="none"${sel("none")}>No role identified (${fmt(none)})</option></optgroup>`;
    return html;
  }

  function instrumentOptions(selected) {
    const sel = (v) => (String(v) === String(selected || "") ? " selected" : "");
    let html = `<option value=""${sel("")}>Any instrument</option>`;
    for (const t of D.types) {
      const xs = D.instruments.filter((x) => x.type === t && x.n > 0).sort((a, b) => a.title.localeCompare(b.title));
      if (!xs.length) continue;
      html += `<optgroup label="${attr(t)}">${xs.map((x) => `<option value="${x.id}"${sel(x.id)}>${esc(x.title)}</option>`).join("")}</optgroup>`;
    }
    return html;
  }

  const disclaimer = `<gcds-notice type="warning" notice-title-tag="h2" notice-title="Check the policy before you act">
      <gcds-text>This prototype finds requirements and the role responsible for each one automatically. It misses some and gets some roles wrong. The policy on the Treasury Board Secretariat website is the authority: every requirement here links to its clause there.</gcds-text>
    </gcds-notice>`;

  // ---------- views ----------

  function viewHome() {
    setTitle("");
    const s = D.summary;
    const groupBlocks = D.groups
      .filter((g) => g !== "Other roles")
      .map((g) => {
        const rs = D.roles.filter((r) => r.group === g && r.n > 0).sort((a, b) => b.n - a.n);
        if (!rs.length) return "";
        const top = rs.slice(0, 5);
        return `<div class="role-group">
          <h3>${esc(g)}</h3>
          <ul class="link-list">${top.map((r) => `<li><a href="${href("role/" + r.id)}">${esc(r.name)}</a> <span class="muted">${plural(r.n, "requirement")}</span></li>`).join("")}</ul>
          ${rs.length > top.length ? `<gcds-text size="small"><a href="${href("roles", { group: slug(g) })}">${plural(rs.length - top.length, "more role")}</a></gcds-text>` : ""}
        </div>`;
      })
      .join("");

    app.innerHTML = `
      <gcds-heading tag="h1">Find the policy requirements that apply to you</gcds-heading>
      <gcds-text character-limit>Treasury Board policies, directives and standards assign responsibilities to specific roles: deputy heads, chief financial officers, managers, employees and many more. This explorer lists ${fmt(s.items)} requirements from ${fmt(s.instrumentsWithItems)} Treasury Board instruments, each tagged with the role responsible for it, so you can see what applies to yours.</gcds-text>

      <form class="search-box" id="home-search" role="search">
        <gcds-input input-id="home-q" name="q" type="search" label="Search the requirements" hint="For example: telework, travel, contracting, privacy, accessibility."></gcds-input>
        <gcds-button type="submit">Search</gcds-button>
      </form>

      <gcds-heading tag="h2">Start with your role</gcds-heading>
      <div class="role-groups">${groupBlocks}</div>
      <gcds-text><a href="${href("roles")}">See all ${D.roles.filter((r) => r.n).length} roles</a> · <a href="${href("instruments")}">Browse by policy instrument</a></gcds-text>

      ${disclaimer}

      <gcds-text size="small" text-role="secondary">Newest policy version in the data: ${esc(D.latestVersionDate)}. Data built ${esc(D.built)}.</gcds-text>`;

    document.getElementById("home-search").addEventListener("submit", (e) => {
      e.preventDefault();
      const q = document.querySelector("#home-search gcds-input").value || "";
      location.hash = href("requirements", { q: q.trim() });
    });
  }

  function slug(s) {
    return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  function readFilters(params) {
    return {
      q: params.get("q") || "",
      role: params.get("role") || "",
      sub: params.get("sub") !== "0",
      inst: params.get("inst") || "",
      type: params.get("type") || "",
      mod: params.get("mod") || "",
      mand: params.get("mand") === "1",
      resp: params.get("resp") === "1",
    };
  }

  function filtersToParams(f) {
    return { q: f.q, role: f.role, sub: f.sub ? "" : "0", inst: f.inst, type: f.type, mod: f.mod, mand: f.mand ? "1" : "", resp: f.resp ? "1" : "" };
  }

  function viewRequirements(params, fixedRole) {
    const f = readFilters(params);
    if (fixedRole) f.role = String(fixedRole);
    const role = f.role && f.role !== "none" ? D.roleById.get(Number(f.role)) : null;
    let shown = PAGE_SIZE;

    const head = fixedRole
      ? roleHeader(role)
      : `<gcds-heading tag="h1">Requirements</gcds-heading>
         <gcds-text character-limit>Filter by your role, a policy instrument or a word. Each requirement links to its clause on the Treasury Board Secretariat website.</gcds-text>`;

    const sel = (v, cur) => (v === cur ? " selected" : "");
    const checks = [
      { id: "f-sub", label: "Include more specific roles", hint: "For example, Travellers when you pick Employees.", value: "sub", checked: f.sub },
      { id: "f-mand", label: "Only policies, directives, standards and frameworks", hint: "Leave out guidelines and guides, which give advice rather than set requirements.", value: "mand", checked: f.mand },
    ];
    if (D.hasItemTypes) checks.push({ id: "f-resp", label: "Only responsibilities", hint: "Hide entitlements, definitions and context.", value: "resp", checked: f.resp });

    app.innerHTML = `
      ${fixedRole ? `<gcds-breadcrumbs hide-canada-link><gcds-breadcrumbs-item href="#/">Explorer</gcds-breadcrumbs-item><gcds-breadcrumbs-item href="#/roles">Roles</gcds-breadcrumbs-item></gcds-breadcrumbs>` : ""}
      ${head}
      <div class="layout">
        <aside class="filters" aria-label="Filters">
          <gcds-heading tag="h2" margin-top="0">Filter</gcds-heading>
          <p class="to-results"><gcds-button button-role="secondary" size="small" id="f-jump">Skip to results</gcds-button></p>
          <gcds-input input-id="f-q" name="q" type="search" label="Search" value="${attr(f.q)}"></gcds-input>
          ${fixedRole ? "" : `<gcds-select select-id="f-role" name="role" label="Role">${roleOptions(f.role)}</gcds-select>`}
          <gcds-select select-id="f-type" name="type" label="Instrument type">
            <option value="">Any type</option>
            ${D.types.map((t) => `<option value="${attr(t)}"${sel(t, f.type)}>${esc(t)}</option>`).join("")}
          </gcds-select>
          <gcds-select select-id="f-inst" name="inst" label="Instrument">${instrumentOptions(f.inst)}</gcds-select>
          <gcds-select select-id="f-mod" name="mod" label="Wording" hint="Many requirements use none of these words.">
            <option value="">Any wording</option>
            <option value="must"${sel("must", f.mod)}>“must”</option>
            <option value="should"${sel("should", f.mod)}>“should”</option>
            <option value="may"${sel("may", f.mod)}>“may”</option>
          </gcds-select>
          <gcds-checkboxes name="flags" legend="Options" hide-legend options='${attr(JSON.stringify(checks))}'></gcds-checkboxes>
          <gcds-button button-role="secondary" id="f-clear" size="small">Clear filters</gcds-button>
        </aside>
        <div class="results">
          <div id="r-summary"></div>
          <div id="r-list"></div>
          <div id="r-more"></div>
        </div>
      </div>`;

    const update = (replace) => {
      const p = filtersToParams(f);
      if (fixedRole) delete p.role;
      const h = href(fixedRole ? "role/" + fixedRole : "requirements", p);
      if (replace) history.replaceState(null, "", h);
      shown = PAGE_SIZE;
      renderResults();
    };

    let results = [];
    const renderResults = () => {
      results = filterItems(f);
      const terms = termsOf(f.q);
      const instCount = new Set(results.map((it) => it.inst)).size;
      const sum = document.getElementById("r-summary");
      let summary = `<p class="result-count"><strong>${plural(results.length, "requirement")}</strong> in ${plural(instCount, "instrument")}</p>`;
      if (results.length && instCount > 1) {
        const counts = new Map();
        results.forEach((it) => counts.set(it.inst, (counts.get(it.inst) || 0) + 1));
        const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]);
        summary += `<gcds-details details-title="Which instruments these come from">
          <table class="table"><thead><tr><th scope="col">Instrument</th><th scope="col">Type</th><th scope="col" class="num">Requirements</th></tr></thead><tbody>
          ${rows.map(([idx, n]) => {
            const x = D.instruments[idx];
            return `<tr><td><a href="#" data-inst="${x.id}">${esc(x.title)}</a></td><td>${esc(x.type)}</td><td class="num">${fmt(n)}</td></tr>`;
          }).join("")}
          </tbody></table></gcds-details>`;
      }
      sum.innerHTML = summary;
      sum.querySelectorAll("a[data-inst]").forEach((a) =>
        a.addEventListener("click", (e) => {
          e.preventDefault();
          f.inst = a.dataset.inst;
          const s = document.querySelector("gcds-select[name=inst]");
          if (s) s.value = f.inst;
          update(true);
          document.getElementById("r-list").scrollIntoView({ behavior: "smooth" });
        })
      );
      const list = document.getElementById("r-list");
      list.innerHTML = results.length
        ? groupedByInstrument(results.slice(0, shown), { terms })
        : `<gcds-notice type="info" notice-title-tag="h2" notice-title="No requirements match"><gcds-text>Try fewer words, or clear a filter. About ${Math.round((100 * (D.summary.items - D.summary.itemsWithRole)) / D.summary.items)}% of requirements have no role identified yet; choose “No role identified” to see them.</gcds-text></gcds-notice>`;
      renderMore();
    };

    const moreButton = () => results.length > shown
      ? `<gcds-button button-role="secondary" id="r-more-btn">Show ${fmt(Math.min(PAGE_SIZE, results.length - shown))} more (${fmt(results.length - shown)} left)</gcds-button>`
      : "";
    const renderMore = () => {
      const more = document.getElementById("r-more");
      more.innerHTML = moreButton();
      const btn = document.getElementById("r-more-btn");
      if (!btn) return;
      btn.addEventListener("click", () => {
        const from = shown;
        shown += PAGE_SIZE;
        // Re-render the list (an instrument's group can continue past the boundary).
        document.getElementById("r-list").innerHTML = groupedByInstrument(results.slice(0, shown), { terms: termsOf(f.q) });
        renderMore();
        document.getElementById("item-" + results[from].i)?.querySelector("a")?.focus();
      });
    };

    const bind = (name, key, transform) => {
      const el = app.querySelector(`[name=${name}]`);
      if (el) onValue(el, (v) => { f[key] = transform ? transform(v) : v || ""; update(true); });
    };
    const qEl = app.querySelector("gcds-input[name=q]");
    onValue(qEl, debounce((v) => { if ((v || "") !== f.q) { f.q = v || ""; update(true); } }, 200));
    bind("role", "role");
    bind("type", "type");
    bind("inst", "inst");
    bind("mod", "mod");
    const cb = app.querySelector("gcds-checkboxes[name=flags]");
    onValue(cb, () => {
      const v = [].concat(cb.value || []);
      f.sub = v.includes("sub");
      f.mand = v.includes("mand");
      f.resp = v.includes("resp");
      update(true);
    });
    document.getElementById("f-jump").addEventListener("click", () => document.getElementById("r-summary").scrollIntoView());
    document.getElementById("f-clear").addEventListener("click", () => {
      location.hash = fixedRole ? href("role/" + fixedRole) : href("requirements");
    });

    renderResults();
  }

  function roleHeader(role) {
    if (!role) return `<gcds-heading tag="h1">Role not found</gcds-heading>`;
    setTitle(role.name);
    const parent = role.parent ? D.roleById.get(role.parent) : null;
    const kids = role.children.map((id) => D.roleById.get(id));
    return `<gcds-heading tag="h1">${esc(role.name)}</gcds-heading>
      <gcds-text character-limit>${plural(role.n, "requirement")} in ${plural(role.inst.size, "instrument")} name this role as responsible.
      ${parent ? ` This role is a subset of <a href="${href("role/" + parent.id)}">${esc(parent.name)}</a>, whose requirements may also apply to you.` : ""}
      ${kids.length ? ` More specific roles within it: ${kids.map((k) => `<a href="${href("role/" + k.id)}">${esc(k.name)}</a>`).join(", ")}.` : ""}</gcds-text>`;
  }

  function viewRole(id, params) {
    const role = D.roleById.get(Number(id));
    if (!role) {
      app.innerHTML = roleHeader(null);
      return;
    }
    viewRequirements(params, role.id);
  }

  function viewRoles(params) {
    setTitle("Roles");
    const blocks = D.groups.map((g) => {
      const rs = D.roles.filter((r) => r.group === g && r.n > 0);
      if (!rs.length) return "";
      // Parents first, then their subsets right after them.
      const ordered = [];
      const inGroup = new Set(rs.map((r) => r.id));
      rs.filter((r) => !r.parent || !inGroup.has(r.parent))
        .sort((a, b) => a.name.localeCompare(b.name))
        .forEach((r) => {
          ordered.push([r, 0]);
          rs.filter((c) => c.parent === r.id).sort((a, b) => a.name.localeCompare(b.name)).forEach((c) => ordered.push([c, 1]));
        });
      return `<section id="group-${attr(slug(g))}">
        <gcds-heading tag="h2">${esc(g)}</gcds-heading>
        <table class="table"><thead><tr><th scope="col">Role</th><th scope="col" class="num">Requirements</th><th scope="col" class="num">Instruments</th></tr></thead><tbody>
        ${ordered.map(([r, depth]) => {
          const parent = r.parent ? D.roleById.get(r.parent) : null;
          return `<tr><td class="${depth ? "indent" : ""}"><a href="${href("role/" + r.id)}">${esc(r.name)}</a>${parent && !depth ? ` <span class="muted">(subset of ${esc(parent.name)})</span>` : ""}</td><td class="num">${fmt(r.n)}</td><td class="num">${fmt(r.inst.size)}</td></tr>`;
        }).join("")}
        </tbody></table></section>`;
    }).join("");
    const none = D.items.filter((it) => it.role == null).length;
    app.innerHTML = `
      <gcds-heading tag="h1">Roles</gcds-heading>
      <gcds-text character-limit>Each requirement is matched to a role from a list of ${D.roles.length} roles that Treasury Board instruments use. Indented roles are subsets: if you are a traveller, the requirements for employees apply to you too. ${fmt(none)} requirements have no role identified; you can <a href="${href("requirements", { role: "none" })}">browse those</a>.</gcds-text>
      ${blocks}`;
    const g = params.get("group");
    if (g) setTimeout(() => document.getElementById("group-" + g)?.scrollIntoView(), 0);
  }

  function viewInstruments(params) {
    setTitle("Instruments");
    const q = params.get("q") || "";
    app.innerHTML = `
      <gcds-heading tag="h1">Policy instruments</gcds-heading>
      <gcds-text character-limit>Policies, directives and standards set requirements. Guidelines and guides give advice. Instruments with no requirements listed are mostly guidance, or use a layout the labeller can't read yet.</gcds-text>
      <gcds-input input-id="i-q" name="iq" type="search" label="Filter instruments by title" value="${attr(q)}"></gcds-input>
      <div id="i-list"></div>`;
    const render = (q) => {
      const t = q.toLowerCase();
      const html = D.types.map((type) => {
        const xs = D.instruments.filter((x) => x.type === type && (!t || x.title.toLowerCase().includes(t))).sort((a, b) => a.title.localeCompare(b.title));
        if (!xs.length) return "";
        return `<gcds-heading tag="h2">${esc(type === "Policy" ? "Policies" : type + "s")} <span class="muted">(${xs.length})</span></gcds-heading>
          <table class="table"><thead><tr><th scope="col">Instrument</th><th scope="col">Version date</th><th scope="col" class="num">Requirements</th><th scope="col" class="num">With a role</th></tr></thead><tbody>
          ${xs.map((x) => `<tr><td><a href="${href("instrument/" + x.id)}">${esc(x.title)}</a></td><td>${esc(x.date)}</td><td class="num">${x.n ? fmt(x.n) : '<span class="muted">none found</span>'}</td><td class="num">${x.n ? fmt(x.nRole) : ""}</td></tr>`).join("")}
          </tbody></table>`;
      }).join("");
      document.getElementById("i-list").innerHTML = html || `<gcds-text>No instruments match.</gcds-text>`;
    };
    const el = app.querySelector("gcds-input[name=iq]");
    onValue(el, debounce((v) => { history.replaceState(null, "", href("instruments", { q: v || "" })); render(v || ""); }, 150));
    render(q);
  }

  function viewInstrument(id) {
    const inst = D.instById.get(Number(id));
    if (!inst) {
      app.innerHTML = `<gcds-heading tag="h1">Instrument not found</gcds-heading><gcds-text><a href="#/instruments">See all instruments</a></gcds-text>`;
      return;
    }
    setTitle(inst.title);
    const idx = D.instruments.indexOf(inst);
    const items = D.items.filter((it) => it.inst === idx);
    const byRole = new Map();
    items.forEach((it) => byRole.set(it.role, (byRole.get(it.role) || 0) + 1));
    const roleRows = [...byRole.entries()].sort((a, b) => (a[0] == null) - (b[0] == null) || b[1] - a[1]);
    const rel = (ids) => ids.map((i) => D.instById.get(i)).filter(Boolean).sort((a, b) => (D.typeRank[a.type] - D.typeRank[b.type]) || a.title.localeCompare(b.title))
      .map((x) => `<li><a href="${href("instrument/" + x.id)}">${esc(x.title)}</a> <span class="muted">${esc(x.type)}</span></li>`).join("");

    // Items grouped by section, then topic.
    let body = "";
    let sec = null, topic = null;
    for (const it of items) {
      if (it.section !== sec) {
        if (sec !== null) body += "</ol>";
        sec = it.section; topic = null;
        body += `<gcds-heading tag="h3">${esc(sec || "Requirements")}</gcds-heading><ol class="items">`;
      }
      if (it.topic && it.topic !== topic && it.topic !== it.section) {
        topic = it.topic;
        body += `</ol><h4 class="topic">${esc(topic)}</h4><ol class="items">`;
      }
      body += itemHTML({ ...it, section: "", topic: "" }, { terms: [], inInstrument: true });
    }
    if (sec !== null) body += "</ol>";

    app.innerHTML = `
      <gcds-breadcrumbs hide-canada-link><gcds-breadcrumbs-item href="#/">Explorer</gcds-breadcrumbs-item><gcds-breadcrumbs-item href="#/instruments">Instruments</gcds-breadcrumbs-item></gcds-breadcrumbs>
      <gcds-heading tag="h1">${esc(inst.title)}</gcds-heading>
      <p class="inst-meta">${typeTag(inst)} <span>Version date: ${esc(inst.date || "unknown")}</span>
        <gcds-link href="${attr(inst.url)}" external>Read it on the Treasury Board Secretariat website</gcds-link></p>
      ${inst.mandatory ? "" : `<gcds-text character-limit>This is guidance. It gives advice and context; any requirements it describes come from the policies and directives it supports.</gcds-text>`}
      <div class="inst-overview">
        <div>
          <gcds-heading tag="h2">Who is responsible</gcds-heading>
          ${items.length ? `<table class="table"><thead><tr><th scope="col">Role</th><th scope="col" class="num">Requirements</th></tr></thead><tbody>
            ${roleRows.map(([rid, n]) => {
              const r = rid != null ? D.roleById.get(rid) : null;
              const link = href("requirements", { role: rid == null ? "none" : rid, inst: inst.id, sub: "0" });
              return `<tr><td><a href="${link}">${esc(roleLabel(r))}</a></td><td class="num">${fmt(n)}</td></tr>`;
            }).join("")}
          </tbody></table>` : `<gcds-text>No requirements were found in this instrument. It may be guidance, or use a layout the labeller can't read yet.</gcds-text>`}
        </div>
        <div>
          ${inst.parents.length ? `<gcds-heading tag="h2">Part of</gcds-heading><ul class="link-list">${rel(inst.parents)}</ul>` : ""}
          ${inst.children.length ? `<gcds-heading tag="h2">Instruments under it</gcds-heading><ul class="link-list">${rel(inst.children)}</ul>` : ""}
        </div>
      </div>
      ${items.length ? `<gcds-heading tag="h2">All ${plural(items.length, "requirement")}</gcds-heading>${body}` : ""}`;
  }

  function viewAbout() {
    setTitle("About");
    const s = D.summary;
    app.innerHTML = `
      <gcds-heading tag="h1">About this prototype</gcds-heading>
      <gcds-text character-limit>This explorer helps people who work in the Government of Canada find the Treasury Board policy requirements that apply to their role. It is an early prototype, in English only, and is not an official Government of Canada product.</gcds-text>

      <gcds-heading tag="h2">Where the data comes from</gcds-heading>
      <gcds-text character-limit>The <a href="https://github.com/lchski/requirement-responsibility-labeller">requirement responsibility labeller</a> reads each instrument in the <a href="https://www.tbs-sct.canada.ca/pol/index-eng.aspx">Treasury Board policy suite</a>, as archived by <a href="https://github.com/PatLittle/TBS-Policy-Hawk">TBS Policy Hawk</a>. It breaks the requirements chapters and appendices into individual items and works out who each item is addressed to from the sentence that introduces it, for example “Chief financial officers are responsible for:”. It then matches that phrase to a list of roles.</gcds-text>
      <ul class="facts">
        <li>${fmt(s.instruments)} instruments read, ${fmt(s.instrumentsWithItems)} with requirements found</li>
        <li>${fmt(s.items)} requirements, ${fmt(s.itemsWithRole)} (${Math.round((100 * s.itemsWithRole) / s.items)}%) matched to a role</li>
        <li>Newest policy version: ${esc(D.latestVersionDate)}</li>
        ${s.listedBehindOrMissing != null ? `<li>${fmt(s.listedBehindOrMissing)} of the ${fmt(s.listedInstruments)} instruments TBS lists are missing or out of date in the archive</li>` : ""}
      </ul>

      <gcds-heading tag="h2">Known limits</gcds-heading>
      <ul class="facts">
        <li>Some items aren't requirements: entitlements, definitions and descriptive text, especially in appendices and guidelines.</li>
        <li>About ${Math.round((100 * (s.items - s.itemsWithRole)) / s.items)}% of items have no role identified, mostly appendices written as bare instructions.</li>
        <li>A role match is only as good as the sentence it came from. “As written” on each item shows the original wording.</li>
        <li>Requirements that apply to everyone in a department (for example, every employee who handles information) are often addressed to the deputy head, who then assigns them. Check the deputy head and manager roles too.</li>
      </ul>

      <gcds-heading tag="h2">How it's built</gcds-heading>
      <gcds-text character-limit>A static site, rebuilt from the labeller's output whenever it changes and published with GitHub Pages. Interface components come from the <a href="https://design-system.canada.ca/">GC Design System</a> by the Canadian Digital Service. The data file behind this page is <a href="data/explorer.json">explorer.json</a>.</gcds-text>`;
  }

  // ---------- router ----------

  function route() {
    if (!D) return;
    const { view, arg, params } = parseHash();
    setNav(view);
    switch (view) {
      case "home": viewHome(); break;
      case "requirements": setTitle("Requirements"); viewRequirements(params); break;
      case "role": viewRole(arg, params); break;
      case "roles": viewRoles(params); break;
      case "instruments": viewInstruments(params); break;
      case "instrument": viewInstrument(arg); break;
      case "about": viewAbout(); break;
      default: viewHome();
    }
    window.scrollTo(0, 0);
  }

  window.addEventListener("hashchange", route);
  load()
    .then((d) => { D = d; route(); })
    .catch((err) => {
      app.innerHTML = `<gcds-notice type="danger" notice-title-tag="h2" notice-title="The data didn't load"><gcds-text>${esc(err.message)}. If you're running this locally, build the data first with <code>python explorer/build.py</code> and serve the <code>explorer/site</code> folder over HTTP.</gcds-text></gcds-notice>`;
    });
})();
