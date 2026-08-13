(function () {
  // カード単位 (.career-ladder__step 等) も [data-reveal] の親セクションとは
  // 独立に個別監視する。親セクションだけを監視すると、背の高いセクション
  // (career-ladder / flow 等) ではセクション先頭が視界に入った瞬間に配下の
  // カード全部が「表示済み」判定され、実際にカードが画面に現れる頃には
  // アニメーションがとっくに完了して見える (=何も動いて見えない) 実害があった。
  var revealEls = document.querySelectorAll(
    '[data-reveal], .career-ladder__step, .category-card, .mission-card, .flow__step, .faq__item'
  );
  if (!revealEls.length) return;

  // 万一この関数内で例外が起きても、`.js` 付与で opacity:0 になった要素が
  // 永久に非表示のまま残らないよう、失敗時は必ず表示状態にフォールバックする。
  try {
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion || !('IntersectionObserver' in window)) {
      revealEls.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }

    // .category-card の transition-delay は CSS の nth-child 指定 (6枚固定
    // 前提、7枚目以降は catch-all で一律 650ms) だと、募集職種が増えるたびに
    // 後半の行がまとめて同時出現するようになり「複数カードが同時にドンと出る」
    // 「出現完了(650ms delay + 1100ms transition = 1750ms)まで間延びして遅い」
    // という体感を生む(2026-08-13 決裁者フィードバックで発覚、実測時点で
    // 17枚中12枚が同一delayになっていた)。列数はブレークポイントで1/2/3に
    // 変わるため、行内の列位置(index % columns)基準で 130ms 刻みの delay を
    // 動的付与し、行数に依存せず常に横方向へ滑らかに現れるようにする。
    document.querySelectorAll('.category-grid').forEach(function (grid) {
      var columns = window.matchMedia('(min-width: 1024px)').matches ? 3
        : window.matchMedia('(min-width: 640px)').matches ? 2
        : 1;
      var cards = grid.querySelectorAll('.category-card');
      cards.forEach(function (card, i) {
        card.style.transitionDelay = (i % columns) * 130 + 'ms';
      });
    });

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.01, rootMargin: '0px 0px -15% 0px' });

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
  // そのため実際の画像サイズと hero の実寸を実測し、余白 (BUFFER) を追加しても
  // background-size:cover が幅基準のまま (=見た目の拡大なし) であることを確認できた
  // 場合のみ視差を有効化する。hero の高さは viewport 幅依存 (clamp) のため、
  // リサイズ・端末回転のたびに再判定する (一度だけの判定だと、有効化後にリサイズで
  // 危険な比率に転んだ場合バッファが残ったまま無防備になる)。
  var hero = document.querySelector('.hero');
  var heroBg = hero && hero.querySelector('.hero__bg');
  if (!hero || !heroBg) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var BUFFER = 60;
  var PARALLAX_RATIO = 0.2;
  var MAX_OFFSET = BUFFER - 5; // 余白 (BUFFER) 未満に必ず収める
  var ticking = false;
  var scrollBound = false;
  var parallaxEnabled = false;
  var io = null;
  var probeWidth = 0;
  var probeHeight = 0;

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
    if (scrollBound) return;
    scrollBound = true;
    heroBg.style.willChange = 'transform';
    window.addEventListener('scroll', onScroll, { passive: true });
    updateParallax();
  }

  function unbindScroll() {
    if (!scrollBound) return;
    scrollBound = false;
    window.removeEventListener('scroll', onScroll);
    heroBg.style.willChange = 'auto';
  }

  function enableParallax() {
    if (parallaxEnabled) return;
    parallaxEnabled = true;
    heroBg.style.top = '-' + BUFFER + 'px';
    heroBg.style.bottom = '-' + BUFFER + 'px';
    // ヒーローが画面に近い間だけ scroll リスナーを張る (ページ全体をスクロールする
    // 間ずっと待ち受けるコストを避ける)。IntersectionObserver 自体は既存の
    // reveal 演出と同じ仕組みを再利用。
    if ('IntersectionObserver' in window) {
      io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) { bindScroll(); } else { unbindScroll(); }
        });
      }, { rootMargin: '50% 0px 50% 0px' });
      io.observe(hero);
    } else {
      bindScroll();
    }
  }

  function disableParallax() {
    if (!parallaxEnabled) return;
    parallaxEnabled = false;
    if (io) { io.disconnect(); io = null; }
    unbindScroll();
    heroBg.style.top = '';
    heroBg.style.bottom = '';
    heroBg.style.transform = 'none';
  }

  function recheckSafety() {
    try {
      if (!probeWidth || !probeHeight) return;
      var heroRect = hero.getBoundingClientRect();
      var widthScale = heroRect.width / probeWidth;
      var heightScaleWithBuffer = (heroRect.height + BUFFER * 2) / probeHeight;
      // 余白込みで高さ基準に転ぶ (=画像が拡大される) 場合は無効化する。
      if (heightScaleWithBuffer <= widthScale) {
        enableParallax();
      } else {
        disableParallax();
      }
    } catch (e) {
      disableParallax();
    }
  }

  var probe = new Image();
  probe.onload = function () {
    probeWidth = probe.naturalWidth;
    probeHeight = probe.naturalHeight;
    recheckSafety();
  };
  // 画像読み込み失敗時は probeWidth/Height が 0 のまま = 視差は有効化されない
  // (安全側にフォールバック、hero__bg は静的な cover 表示のまま)。
  probe.src = 'assets/img/sky-hero.jpg';

  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(recheckSafety, 200);
  }, { passive: true });
})();

(function () {
  // キャリアモデルの職種タブ切替 (介護施設・介護スタッフ / 訪問介護・ホームヘルパー)。
  // 非選択パネルの hidden 化はこの JS が初期化された時点で行う (HTML に hidden を
  // 静的記述すると JS 無効/失敗時に訪問介護側が完全に閲覧不能になるため、
  // JS が動く場合のみタブ切替として振る舞い、動かない場合は両パネルとも静的表示のまま残す)。
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.career-tabs__btn'));
  if (!tabs.length) return;

  function activate(tab) {
    tabs.forEach(function (t) {
      var selected = t === tab;
      t.setAttribute('aria-selected', selected ? 'true' : 'false');
      t.tabIndex = selected ? 0 : -1;
      var panel = document.getElementById(t.getAttribute('aria-controls'));
      if (!panel) return;
      panel.hidden = !selected;
      if (selected) {
        // hidden 中はカードが IntersectionObserver に検知されず reveal 演出が
        // 発火しない場合があるため、タブ切替時は表示済み扱いにして確実に見せる。
        panel.querySelectorAll('.career-ladder__step').forEach(function (el) {
          el.classList.add('is-visible');
        });
      }
    });
    tab.focus();
  }

  tabs.forEach(function (tab, index) {
    tab.addEventListener('click', function () { activate(tab); });
    tab.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      e.preventDefault();
      var next = e.key === 'ArrowRight'
        ? tabs[(index + 1) % tabs.length]
        : tabs[(index - 1 + tabs.length) % tabs.length];
      activate(next);
    });
  });

  var initialTab = tabs.filter(function (t) { return t.getAttribute('aria-selected') === 'true'; })[0] || tabs[0];
  tabs.forEach(function (t) {
    var panel = document.getElementById(t.getAttribute('aria-controls'));
    if (panel && t !== initialTab) panel.hidden = true;
    if (t !== initialTab) t.tabIndex = -1;
  });
})();
