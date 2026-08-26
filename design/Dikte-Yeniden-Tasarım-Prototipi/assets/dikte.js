(function () {
  "use strict";

  var S = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
  var ICONS = {
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0"/><path d="M12 17.5V21"/>',
    micOff: '<path d="M15 9.5V6a3 3 0 0 0-5.6-1.5"/><path d="M9 9v2a3 3 0 0 0 4.6 2.5"/><path d="M5.5 11a6.5 6.5 0 0 0 10.9 4.8"/><path d="M12 17.5V21"/><path d="m4 4 16 16"/>',
    sliders: '<path d="M4 7.5h9"/><path d="M17.5 7.5H20"/><circle cx="15.2" cy="7.5" r="2.2"/><path d="M4 16.5h2.5"/><path d="M11 16.5h9"/><circle cx="8.7" cy="16.5" r="2.2"/>',
    plug: '<path d="M9 3v4.5"/><path d="M15 3v4.5"/><path d="M6.5 7.5h11V11a5.5 5.5 0 0 1-11 0z"/><path d="M12 16.5V21"/>',
    eraser: '<path d="m8 20.5-4-4a2 2 0 0 1 0-2.8l8.7-8.7a2 2 0 0 1 2.8 0l4 4a2 2 0 0 1 0 2.8l-7.2 7.2a2.4 2.4 0 0 1-1.7.7z"/><path d="m8.5 9.5 6.5 6.5"/><path d="M20.5 20.5H11"/>',
    terminal: '<path d="m4 17 6-5-6-5"/><path d="M12 19h8"/>',
    users: '<circle cx="9" cy="7.5" r="3.5"/><path d="M2.5 20.5v-.8a6.2 6.2 0 0 1 6.2-6.2h.6a6.2 6.2 0 0 1 6.2 6.2v.8"/><path d="M15.8 4.4a3.5 3.5 0 0 1 0 6.3"/><path d="M19.5 13.7a6.2 6.2 0 0 1 2 4.6v2.2"/>',
    fileText: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h4"/>',
    fileAudio: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 15.5v-2"/><path d="M12 17v-5"/><path d="M15 15.5v-2"/>',
    keyboard: '<rect x="3" y="6.5" width="18" height="11" rx="2"/><path d="M7 10.5h.01"/><path d="M10.5 10.5h.01"/><path d="M14 10.5h.01"/><path d="M17.5 10.5h.01"/><path d="M7 14h10"/>',
    history: '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.4"/><path d="M3.5 3.5v5h5"/><path d="M12 8v4.3l2.7 2.7"/>',
    pip: '<rect x="3" y="5" width="18" height="14" rx="2"/><rect x="12" y="11.5" width="6.5" height="4.5" rx="1"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20.5 20.5-4.7-4.7"/>',
    plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
    x: '<path d="m6 6 12 12"/><path d="m18 6-12 12"/>',
    chevD: '<path d="m6 9 6 6 6-6"/>',
    chevR: '<path d="m9 6 6 6-6 6"/>',
    chevL: '<path d="m15 6-6 6 6 6"/>',
    check: '<path d="m4.5 12.5 5 5L19.5 7"/>',
    checkC: '<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.4 4.8-5"/>',
    xC: '<circle cx="12" cy="12" r="8.5"/><path d="m9.2 9.2 5.6 5.6"/><path d="m14.8 9.2-5.6 5.6"/>',
    alert: '<path d="M10.3 4.2 2.9 17a2 2 0 0 0 1.7 3h14.8a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4"/><path d="M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 8h.01"/><path d="M12 11.5V16"/>',
    help: '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.2a2.5 2.5 0 0 1 4.9.7c0 1.6-2.5 2.1-2.5 3.6"/><path d="M12 17h.01"/>',
    dots: '<circle cx="5" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
    copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    trash: '<path d="M4 7h16"/><path d="M9.5 7V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v2"/><path d="m6.5 7 .8 12.1a2 2 0 0 0 2 1.9h5.4a2 2 0 0 0 2-1.9L17.5 7"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    folder: '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3.6L11 7h7.5A2.5 2.5 0 0 1 21 9.5v7a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 16.5z"/>',
    refresh: '<path d="M20.5 12a8.5 8.5 0 1 1-2.6-6.1l2.6 2.5"/><path d="M20.5 3.5v5h-5"/>',
    download: '<path d="M12 3.5V15"/><path d="m7 10 5 5 5-5"/><path d="M4.5 20.5h15"/>',
    upload: '<path d="M12 15V3.5"/><path d="m7 8.5 5-5 5 5"/><path d="M4.5 20.5h15"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>',
    play: '<path d="M8 5.5v13l10-6.5z" fill="currentColor" stroke="none"/>',
    pause: '<rect x="6.5" y="5" width="3.6" height="14" rx="1" fill="currentColor" stroke="none"/><rect x="13.9" y="5" width="3.6" height="14" rx="1" fill="currentColor" stroke="none"/>',
    eye: '<path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    eyeOff: '<path d="M10.6 6c.5-.1.9-.2 1.4-.2 6 0 9.5 6.2 9.5 6.2a17 17 0 0 1-2.7 3.4"/><path d="M6.4 7.3A16.6 16.6 0 0 0 2.5 12S6 18.2 12 18.2c1.6 0 3-.4 4.2-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="m4 4 16 16"/>',
    pencil: '<path d="m14.5 5.5 4 4"/><path d="M4 20l1.2-4.6L16.4 4.2a2 2 0 0 1 2.8 0l.6.6a2 2 0 0 1 0 2.8L8.6 18.8z"/>',
    key: '<circle cx="8" cy="15.5" r="4.2"/><path d="m11 12.5 8.5-8.5"/><path d="M16 7.5 19 10.5"/><path d="M13.5 10 16 12.5"/>',
    globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><path d="M12 3.5c2.6 2.3 4 5.3 4 8.5s-1.4 6.2-4 8.5c-2.6-2.3-4-5.3-4-8.5s1.4-6.2 4-8.5z"/>',
    cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2.5V6"/><path d="M15 2.5V6"/><path d="M9 18v3.5"/><path d="M15 18v3.5"/><path d="M2.5 9H6"/><path d="M2.5 15H6"/><path d="M18 9h3.5"/><path d="M18 15h3.5"/>',
    bell: '<path d="M6.3 9.5a5.7 5.7 0 0 1 11.4 0c0 4.6 1.8 5.8 1.8 5.8H4.5s1.8-1.2 1.8-5.8"/><path d="M10.4 19.5a1.7 1.7 0 0 0 3.2 0"/>',
    wave: '<path d="M4 10v4"/><path d="M8 7v10"/><path d="M12 4v16"/><path d="M16 7v10"/><path d="M20 10v4"/>',
    headphones: '<path d="M4 14.5v-2a8 8 0 0 1 16 0v2"/><path d="M4 14.5h2.2a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/><path d="M20 14.5h-2.2a1 1 0 0 0-1 1v3a1 1 0 0 0 1 1H19a1 1 0 0 0 1-1z"/>',
    monitor: '<rect x="3" y="4.5" width="18" height="12.5" rx="2"/><path d="M8.5 21h7"/><path d="M12 17v4"/>',
    power: '<path d="M12 3v9"/><path d="M18.2 6.6a8.5 8.5 0 1 1-12.4 0"/>',
    restart: '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.4"/><path d="M3.5 3.5v5h5"/>',
    filter: '<path d="M4 5.5h16l-6.2 7.2v4.9l-3.6 1.9v-6.8z"/>',
    calendar: '<rect x="4" y="5.5" width="16" height="15" rx="2"/><path d="M8 3.5v4"/><path d="M16 3.5v4"/><path d="M4 10.5h16"/>',
    tag: '<path d="m3.5 12.6V5.5a2 2 0 0 1 2-2h7.1a2 2 0 0 1 1.4.6l6.5 6.5a2 2 0 0 1 0 2.8l-7.1 7.1a2 2 0 0 1-2.8 0l-6.5-6.5a2 2 0 0 1-.6-1.4z"/><circle cx="8" cy="8" r="1.1" fill="currentColor" stroke="none"/>',
    type: '<path d="M5 6.5V4.5h14v2"/><path d="M12 4.5V19.5"/><path d="M9 19.5h6"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2.5"/>',
    arrowUR: '<path d="M7 17 17 7"/><path d="M8.5 7H17v8.5"/>',
    minus: '<path d="M5.5 12h13"/>',
    square: '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    save: '<path d="M5.5 3.5h10.5l3.5 3.5v12a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4.5 19V5a1.5 1.5 0 0 1 1-1.5z"/><path d="M8 3.5V8h7V3.5"/><path d="M8 20.5v-6h8v6"/>',
    sun: '<circle cx="12" cy="12" r="3.5"/><path d="M12 2.5v2"/><path d="M12 19.5v2"/><path d="m4.6 4.6 1.4 1.4"/><path d="m18 18 1.4 1.4"/><path d="M2.5 12h2"/><path d="M19.5 12h2"/><path d="m4.6 19.4 1.4-1.4"/><path d="m18 6 1.4-1.4"/>',
    moon: '<path d="M20 15.2A8.5 8.5 0 0 1 8.8 4a8.5 8.5 0 1 0 11.2 11.2z"/>'
  };

  function injectIcons(root) {
    (root || document).querySelectorAll("[data-ic]").forEach(function (el) {
      var name = el.getAttribute("data-ic");
      var path = ICONS[name];
      if (path && !el.firstChild) {
        el.innerHTML = S + path + "</svg>";
      }
    });
  }
  window.dkIcons = ICONS;
  window.dkIcon = function (name, cls) {
    return '<span class="ic-wrap' + (cls ? " " + cls : "") + '" data-ic="' + name + '"></span>';
  };

  var waveSeed = 3;
  function rnd() {
    waveSeed = (waveSeed * 16807 + 19) % 2147483647;
    return (waveSeed % 1000) / 1000;
  }
  window.dkWave = function (el, n, dual) {
    if (!el) return;
    var html = "";
    for (var i = 0; i < n; i++) {
      var h = 4 + Math.round(rnd() * 22);
      var d = (rnd() * 0.9).toFixed(2) + "s";
      var dur = (0.7 + rnd() * 0.7).toFixed(2) + "s";
      html += '<i style="--h:' + h + 'px;--d:' + d + ';animation-duration:' + dur + '"></i>';
    }
    if (dual) {
      var html2 = "";
      for (var j = 0; j < n; j++) {
        var h2 = 3 + Math.round(rnd() * 9);
        var d2 = (rnd() * 0.9).toFixed(2) + "s";
        var dur2 = (0.7 + rnd() * 0.7).toFixed(2) + "s";
        html2 += '<b class="b" style="--h:' + h2 + 'px;--d:' + d2 + ';animation-duration:' + dur2 + '"></b>';
      }
      el.innerHTML = '<span class="half">' + html.replace(/<i/g, '<b class="b"').replace(/<\/i>/g, "</b>") + "</span>" + '<span class="half down">' + html2 + "</span>";
    } else {
      el.innerHTML = html;
    }
  };

  function toast(msg, kind) {
    var stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      document.body.appendChild(stack);
    }
    var t = document.createElement("div");
    t.className = "toast" + (kind === "warn" ? " warn" : "");
    t.innerHTML = '<span class="ic-wrap ic" data-ic="' + (kind === "warn" ? "alert" : "check") + '"></span><span></span>';
    t.lastElementChild.textContent = msg;
    stack.appendChild(t);
    injectIcons(stack);
    setTimeout(function () {
      t.style.transition = "opacity .25s ease";
      t.style.opacity = "0";
      setTimeout(function () { t.remove(); }, 260);
    }, 2600);
  }
  window.dkToast = toast;

  function openDialog(id) {
    var sc = document.getElementById(id);
    if (sc) { sc.classList.add("open"); var f = sc.querySelector("button, input, textarea"); if (f) f.focus(); }
  }
  function closeDialog(id) {
    var sc = document.getElementById(id);
    if (sc) sc.classList.remove("open");
  }
  window.dkDialog = { open: openDialog, close: closeDialog };
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") document.querySelectorAll(".scrim.open").forEach(function (s) { s.classList.remove("open"); });
  });
  document.addEventListener("click", function (e) {
    var c = e.target.closest("[data-dialog-close]");
    if (c) closeDialog(c.getAttribute("data-dialog-close"));
    var o = e.target.closest("[data-dialog-open]");
    if (o) openDialog(o.getAttribute("data-dialog-open"));
    if (e.target.classList && e.target.classList.contains("scrim")) e.target.classList.remove("open");
  });

  function busyButton(btn, ms, done) {
    if (!btn || btn.classList.contains("is-busy")) return;
    btn.classList.add("is-busy");
    var old = btn.getAttribute("aria-busy");
    btn.setAttribute("aria-busy", "true");
    setTimeout(function () {
      btn.classList.remove("is-busy");
      if (old === null) btn.removeAttribute("aria-busy"); else btn.setAttribute("aria-busy", old);
      if (done) done();
    }, ms || 900);
  }
  window.dkBusy = busyButton;

  function bindTest(btnSel, statusSel, okMsg) {
    var btn = document.querySelector(btnSel);
    var st = document.querySelector(statusSel);
    if (!btn) return;
    btn.addEventListener("click", function () {
      if (st) { st.innerHTML = '<span class="spin sm"></span> Sınanıyor…'; }
      busyButton(btn, 1100, function () {
        if (st) st.innerHTML = '<span class="ic-wrap ic-s" data-ic="checkC" style="color:var(--ok)"></span> ' + okMsg;
        injectIcons(st);
      });
    });
  }
  window.dkBindTest = bindTest;

  function bindFetch(btnSel, statusSel, okMsg, alsoFill) {
    var btn = document.querySelector(btnSel);
    var st = document.querySelector(statusSel);
    if (!btn) return;
    btn.addEventListener("click", function () {
      if (st) { st.innerHTML = '<span class="spin sm"></span> Model listesi getiriliyor…'; }
      busyButton(btn, 1200, function () {
        if (st) st.innerHTML = '<span class="ic-wrap ic-s" data-ic="checkC" style="color:var(--ok)"></span> ' + okMsg;
        injectIcons(st);
        if (alsoFill) alsoFill();
      });
    });
  }
  window.dkBindFetch = bindFetch;

  function markDirty() {
    document.querySelectorAll(".savebar").forEach(function (b) { b.classList.add("show"); });
  }
  function initSavebar() {
    var bar = document.querySelector(".savebar");
    if (!bar) return;
    var main = document.querySelector(".main");
    if (main) {
      main.addEventListener("input", markDirty);
      main.addEventListener("change", function (e) {
        if (e.target.closest(".savebar")) return;
        markDirty();
      });
    }
    var save = bar.querySelector("[data-save]");
    var reset = bar.querySelector("[data-reset]");
    if (save) save.addEventListener("click", function () {
      bar.classList.remove("show");
      toast("Ayarlar kaydedildi.");
    });
    if (reset) reset.addEventListener("click", function () {
      bar.classList.remove("show");
      toast("Değişiklikler geri alındı.", "warn");
    });
  }

  function initNav() {
    var page = document.body.getAttribute("data-page");
    if (!page) return;
    document.querySelectorAll(".nav-item").forEach(function (a) {
      if (a.getAttribute("data-nav") === page) a.classList.add("active");
    });
  }

  function initGates() {
    document.querySelectorAll("[data-gate]").forEach(function (tg) {
      var input = tg.querySelector("input");
      var targets = document.querySelectorAll(tg.getAttribute("data-gate"));
      function apply() {
        targets.forEach(function (t) { t.classList.toggle("is-off", !input.checked); });
      }
      if (input) {
        input.addEventListener("change", apply);
        apply();
      }
    });
  }

  function comboFromEvent(e) {
    var parts = [];
    if (e.ctrlKey) parts.push("Ctrl");
    if (e.altKey) parts.push("Alt");
    if (e.shiftKey) parts.push("Shift");
    if (e.metaKey) parts.push("Win");
    var k = e.key;
    if (["Control", "Alt", "Shift", "Meta"].indexOf(k) === -1) {
      if (k === " ") k = "Space";
      else if (k.length === 1) k = k.toUpperCase();
      parts.push(k);
      return parts.join("+");
    }
    return null;
  }

  function initHotkeys() {
    document.querySelectorAll(".hotkey").forEach(function (hk) {
      var disp = hk.querySelector(".hk-display");
      var clear = hk.querySelector(".hk-x");
      hk.addEventListener("click", function (e) {
        if (e.target.closest(".hk-x")) return;
        if (hk.classList.contains("rec")) return;
        document.querySelectorAll(".hotkey.rec").forEach(function (o) { o.classList.remove("rec"); o.querySelector(".hk-display").innerHTML = o.getAttribute("data-prev") || ""; });
        hk.setAttribute("data-prev", disp.innerHTML);
        hk.classList.add("rec");
        disp.innerHTML = '<span class="hk-hint">Tuşlara basın…</span>';
        function onKey(ev) {
          ev.preventDefault();
          ev.stopPropagation();
          document.removeEventListener("keydown", onKey, true);
          if (ev.key === "Escape") {
            disp.innerHTML = hk.getAttribute("data-prev") || "";
            hk.classList.remove("rec");
            return;
          }
          var combo = comboFromEvent(ev);
          hk.classList.remove("rec");
          if (combo) {
            disp.innerHTML = combo.split("+").map(function (p) { return '<span class="kbd">' + p + "</span>"; }).join('<span class="hk-hint">+</span>');
            hk.dispatchEvent(new CustomEvent("hotkey:set", { bubbles: true, detail: { combo: combo } }));
          } else {
            disp.innerHTML = hk.getAttribute("data-prev") || "";
          }
        }
        document.addEventListener("keydown", onKey, true);
      });
      if (clear) clear.addEventListener("click", function (e) {
        e.stopPropagation();
        disp.innerHTML = '<span class="kbd add">yok</span>';
        hk.dispatchEvent(new CustomEvent("hotkey:set", { bubbles: true, detail: { combo: "" } }));
      });
    });
  }

  function initSwitches() {
    document.querySelectorAll("[data-switch]").forEach(function (sel) {
      var map = {};
      try { map = JSON.parse(sel.getAttribute("data-switch")); } catch (e) {}
      function apply() {
        Object.keys(map).forEach(function (val) {
          var el = document.querySelector(map[val]);
          if (el) el.hidden = sel.value !== val;
        });
      }
      sel.addEventListener("change", apply);
      apply();
    });
  }

  function initTabs() {
    document.querySelectorAll("[data-tabs]").forEach(function (seg) {
      var panels = {};
      try { panels = JSON.parse(seg.getAttribute("data-tabs")); } catch (e) {}
      seg.querySelectorAll("[data-tab]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          seg.querySelectorAll("[data-tab]").forEach(function (b) {
            b.classList.remove("active");
            b.setAttribute("aria-selected", "false");
          });
          btn.classList.add("active");
          btn.setAttribute("aria-selected", "true");
          Object.keys(panels).forEach(function (key) {
            var el = document.querySelector(panels[key]);
            if (el) el.hidden = btn.getAttribute("data-tab") !== key;
          });
        });
      });
    });
  }

  function initCornerPicker() {
    var pick = document.querySelector(".corner-picker,.corner-pick");
    if (!pick) return;
    var mini = document.querySelector(".mini-screen .mini-ov,.corner-preview .ov");
    var cells = pick.querySelectorAll(".corner-cell,[data-c]");
    cells.forEach(function (cell) {
      cell.addEventListener("click", function () {
        cells.forEach(function (c) { c.classList.remove("active","is-active"); });
        cell.classList.add(cell.classList.contains("corner-cell") ? "active" : "is-active");
        if (mini) {
          var c = cell.getAttribute("data-corner") || cell.getAttribute("data-c");
          mini.style.top = mini.style.bottom = mini.style.left = mini.style.right = "auto";
          if (c.indexOf("t") === 0) mini.style.top = "6px"; else mini.style.bottom = "6px";
          if (c.indexOf("l") === 1 || c === "tl" || c === "bl") mini.style.left = "6px"; else mini.style.right = "6px";
          try { localStorage.setItem("dikte.overlay.corner", c); } catch (e) {}
        }
      });
    });
    var saved = null;
    try { saved = localStorage.getItem("dikte.overlay.corner"); } catch (e) {}
    if (saved) {
      var selected = pick.querySelector('[data-corner="'+saved+'"],[data-c="'+saved+'"]');
      if (selected) selected.click();
    }
  }

  function initMenus() {
    document.querySelectorAll("[data-menu-toggle]").forEach(function (btn) {
      var menu = document.querySelector(btn.getAttribute("data-menu-toggle"));
      if (!menu) return;
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var open = menu.hidden;
        document.querySelectorAll("[data-menu-panel]").forEach(function (m) { m.hidden = true; });
        menu.hidden = !open;
        btn.setAttribute("aria-expanded", String(open));
      });
    });
    document.addEventListener("click", function () {
      document.querySelectorAll("[data-menu-panel]").forEach(function (m) { m.hidden = true; });
      document.querySelectorAll("[data-menu-toggle]").forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
    });
  }

  function initNums() {
    document.querySelectorAll(".num").forEach(function (n) {
      if (n.getAttribute("data-nums")) return;
      n.setAttribute("data-nums", "1");
      n.querySelectorAll(".nbtn").forEach(function (b) {
        b.addEventListener("click", function () {
          var inp = n.querySelector("input");
          if (!inp) return;
          var v = (parseInt(inp.value, 10) || 0) + (parseInt(b.getAttribute("data-step"), 10) || 1);
          var min = inp.getAttribute("min"), max = inp.getAttribute("max");
          if (min !== null && v < +min) v = +min;
          if (max !== null && v > +max) v = +max;
          inp.value = v;
          inp.dispatchEvent(new Event("change", { bubbles: true }));
          inp.dispatchEvent(new Event("input", { bubbles: true }));
        });
      });
    });
  }

  function readTheme() {
    try { return localStorage.getItem("dikte.theme") || "dark"; } catch (e) { return "dark"; }
  }
  function updateThemeControls() {
    var theme = document.documentElement.getAttribute("data-theme") || "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      var next = theme === "dark" ? "light" : "dark";
      btn.setAttribute("aria-label", next === "light" ? "Açık temaya geç" : "Koyu temaya geç");
      btn.setAttribute("title", next === "light" ? "Açık temaya geç" : "Koyu temaya geç");
      btn.setAttribute("aria-pressed", String(theme === "light"));
      var icon = '<span data-ic="' + (theme === "dark" ? "sun" : "moon") + '"></span>';
      var label = btn.classList.contains("theme-control") ? '<span class="theme-label">' + (theme === "dark" ? "Açık tema" : "Koyu tema") + '</span>' : '';
      btn.innerHTML = icon + label;
      injectIcons(btn);
    });
  }
  function applyTheme(theme) {
    theme = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("dikte.theme", theme); } catch (e) {}
    updateThemeControls();
    document.dispatchEvent(new CustomEvent("dk-theme-change", { detail: { theme: theme } }));
  }
  function toggleTheme() { applyTheme((document.documentElement.getAttribute("data-theme") || "dark") === "dark" ? "light" : "dark"); }
  function initTheme() {
    applyTheme(readTheme());
    var foot = document.querySelector(".side-foot");
    if (foot && !foot.querySelector("[data-theme-toggle]")) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "theme-control";
      btn.setAttribute("data-theme-toggle", "true");
      foot.appendChild(btn);
    }
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) { btn.addEventListener("click", toggleTheme); });
    updateThemeControls();
  }

  function init() {
    injectIcons();
    initNav();
    initSavebar();
    initGates();
    initHotkeys();
    initSwitches();
    initTabs();
    initCornerPicker();
    initMenus();
    initNums();
    initTheme();
    document.querySelectorAll("[data-wave]").forEach(function (el) {
      var attr = el.getAttribute("data-wave");
      dkWave(el, parseInt(attr, 10) || 18, attr === "dual");
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  window.DK = {
    inject: injectIcons,
    toast: toast,
    wave: dkWave,
    busy: busyButton,
    markDirty: markDirty,
    openDialog: openDialog,
    closeDialog: closeDialog,
    getTheme: function () { return document.documentElement.getAttribute("data-theme") || "dark"; },
    setTheme: applyTheme,
    toggleTheme: toggleTheme,
    icon: function (name) { return S + (ICONS[name] || "") + "</svg>"; }
  };
})();
