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

(function () {
  // ヒーロー背景の視差スクロール。控えめな移動量 (PARALLAX_RATIO) で、
  // コンテンツより背景がゆっくり動く古典的パララックスを再現する。
  //
  // 固定の viewport 幅ブレークポイントでは安全性を保証できない (実機検証で発覚:
  // background-size:cover は画像の自然サイズと hero の実高さの比率で幅基準/高さ基準が
  // 決まり、閾値は viewport 幅だけで一意に決まらない。sky-hero.jpg はこのプロジェクトで
  // 過去に複数回差し替えられており、画像のアスペクト比が変わるたびに閾値も変わる)。
  // そのため実際の画像サイズと hero の実寸を読み込み後に実測し、余白 (BUFFER) を
  // 追加しても background-size:cover が幅基準のまま (=見た目の拡大なし) であることを
  // 確認できた場合のみ視差を有効化する。
  var hero = document.querySelector('.hero');
  var heroBg = hero && hero.querySelector('.hero__bg');
  if (!hero || !heroBg) return;

  try {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var BUFFER = 60;
    var PARALLAX_RATIO = 0.2;
    var MAX_OFFSET = BUFFER - 5; // 余白 (BUFFER) 未満に必ず収める

    var probe = new Image();
    probe.onload = function () {
      if (!probe.naturalWidth || !probe.naturalHeight) return;
      var heroRect = hero.getBoundingClientRect();
      var widthScale = heroRect.width / probe.naturalWidth;
      var heightScaleWithBuffer = (heroRect.height + BUFFER * 2) / probe.naturalHeight;
      // 余白込みで高さ基準に転ぶ (=画像が拡大される) 場合は視差を有効化しない。
      if (heightScaleWithBuffer > widthScale) return;

      heroBg.style.top = '-' + BUFFER + 'px';
      heroBg.style.bottom = '-' + BUFFER + 'px';
      startParallax();
    };
    probe.src = 'assets/img/sky-hero.jpg';

    function startParallax() {
      var ticking = false;
      var bound = false;

      function updateParallax() {
        ticking = false;
        var offset = Math.max(0, Math.min(window.scrollY * PARALLAX_RATIO, MAX_OFFSET));
        heroBg.style.transform = 'translate3d(0, ' + offset.toFixed(1) + 'px, 0)';
      }

      function onScroll() {
        if (!ticking) {
          ticking = true;
          window.requestAnimationFrame(updateParallax);
        }
      }

      function bindScroll() {
        if (bound) return;
        bound = true;
        heroBg.style.willChange = 'transform';
        window.addEventListener('scroll', onScroll, { passive: true });
        updateParallax();
      }

      function unbindScroll() {
        if (!bound) return;
        bound = false;
        window.removeEventListener('scroll', onScroll);
        heroBg.style.willChange = 'auto';
      }

      // ヒーローが画面に近い間だけ scroll リスナーを張る (ページ全体をスクロールする
      // 間ずっと待ち受けるコストを避ける)。IntersectionObserver 自体は既存の
      // reveal 演出と同じ仕組みを再利用。
      if ('IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) { bindScroll(); } else { unbindScroll(); }
          });
        }, { rootMargin: '50% 0px 50% 0px' });
        io.observe(hero);
      } else {
        bindScroll();
      }
    }
  } catch (e) {
    heroBg.style.transform = 'none';
  }
})();
