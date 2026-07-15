(function () {
  var revealEls = document.querySelectorAll('[data-reveal]');
  if (!revealEls.length) return;

  // 万一この関数内で例外が起きても、`.js` 付与で opacity:0 になった要素が
  // 永久に非表示のまま残らないよう、失敗時は必ず表示状態にフォールバックする。
  try {
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion || !('IntersectionObserver' in window)) {
      revealEls.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.01, rootMargin: '0px 0px -5% 0px' });

    revealEls.forEach(function (el) { observer.observe(el); });
  } catch (e) {
    revealEls.forEach(function (el) { el.classList.add('is-visible'); });
  }
})();
