"use strict";
/* Three ambient beats, all single-property, all on <= 3 elements at a time.
   Nothing here runs per-frame; the only JS that touches a frame is the
   viewer's own renderer, and it only mounts once it is nearly on screen. */
(function () {
  var entries = [].slice.call(document.querySelectorAll(".entry"));
  var hv = document.getElementById("hv");
  var n = entries.length;

  /* 1. the reading band — which entry owns the accent tick */
  var band = new IntersectionObserver(function (rows) {
    rows.forEach(function (r) {
      if (!r.isIntersecting) return;
      entries.forEach(function (e) { e.classList.remove("on"); });
      r.target.classList.add("on");
      var i = entries.indexOf(r.target);
      /* a readout hard-cuts. It does not crossfade. */
      hv.textContent = "ENTRY " + r.target.dataset.n + " / " +
        ("0" + n).slice(-2) + " — " +
        r.target.querySelector(".verb").textContent.trim();
    });
  }, { rootMargin: "-45% 0px -45% 0px" });
  entries.forEach(function (e) { band.observe(e); });

  /* 1b. page dots on mobile — the desktop entry readout is off-screen there,
        and a deck with no position indicator feels endless */
  if (matchMedia("(max-width: 760px)").matches) {
    var pager = document.createElement("div");
    pager.className = "pager";
    var dots = entries.map(function () {
      var i = document.createElement("i");
      pager.appendChild(i);
      return i;
    });
    document.body.appendChild(pager);
    var pageObs = new IntersectionObserver(function (rows) {
      rows.forEach(function (r) {
        if (!r.isIntersecting) return;
        var i = entries.indexOf(r.target);
        dots.forEach(function (d, k) { d.className = k === i ? "on" : ""; });
      });
    }, { rootMargin: "-45% 0px -45% 0px" });
    entries.forEach(function (e) { pageObs.observe(e); });
  }

  /* 2. the viewer mounts AFTER first paint, never before — the fold is type
        and a static SVG, so the canvas can never be the thing keeping the
        page from painting. 600px of rootMargin means it is already true at
        load, so it costs no wait. */
  var mount = document.getElementById("viewer-mount");
  if (mount) {
    var once = new IntersectionObserver(function (rows, obs) {
      if (!rows[0].isIntersecting) return;
      obs.disconnect();
      var tpl = document.getElementById("viewer-src");
      mount.innerHTML = "";
      mount.appendChild(tpl.content.cloneNode(true));
      /* the fragment ships inert <script>; cloning does not execute it */
      [].forEach.call(mount.querySelectorAll("script"), function (old) {
        var s = document.createElement("script");
        s.textContent = old.textContent;
        old.parentNode.replaceChild(s, old);
      });
    }, { rootMargin: "600px" });
    once.observe(mount);
  }
})();
