(function () {
  'use strict';

  var root = document.querySelector('.job-search');
  if (!root) return;

  var panel = document.getElementById('job-search-panel');
  var mapWrap = document.getElementById('job-map-wrap');
  var mapPanelsEl = document.getElementById('job-map-panels');
  var listCol = document.getElementById('job-search-list-col');
  var countEl = document.getElementById('job-search-count');
  var freewordEl = document.getElementById('job-search-freeword');
  var gpsBtn = document.getElementById('job-search-gps');
  var clearBtn = document.getElementById('job-search-clear');
  var gpsStatus = document.getElementById('job-search-gps-status');
  var facilityFilterBar = document.getElementById('job-search-facility-filter');
  var facilityFilterLabel = document.getElementById('job-search-facility-filter-label');
  var facilityFilterClear = document.getElementById('job-search-facility-filter-clear');
  var emptyMessage = document.getElementById('job-search-empty');

  // エリア(福岡/鹿児島)ごとに拡大パネルを分けて表示する(2026-07-24改訂)ため、
  // 地図の描画先は単一要素ではなくエリア別の複数要素になる。
  var diagramEls = {};
  if (mapPanelsEl) {
    Array.prototype.forEach.call(mapPanelsEl.querySelectorAll('.job-map-diagram'), function (el) {
      diagramEls[el.getAttribute('data-area')] = el;
    });
  }

  if (!panel || !mapWrap || !mapPanelsEl || !listCol || !countEl) return;

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var EARTH_RADIUS_KM = 6371;
  function haversineKm(lat1, lng1, lat2, lng2) {
    var toRad = function (d) { return (d * Math.PI) / 180; };
    var dLat = toRad(lat2 - lat1);
    var dLng = toRad(lng2 - lng1);
    var a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return EARTH_RADIUS_KM * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  fetch('assets/data/jobs.json')
    .then(function (res) {
      if (!res.ok) throw new Error('jobs.json fetch failed: ' + res.status);
      return res.json();
    })
    .then(function (data) {
      init(data);
    })
    .catch(function () {
      // データ取得失敗時は検索UI一式を出さず、既存の34カード全表示のままにする。
    });

  function init(data) {
    var facilities = data.facilities || {};
    var jobs = data.jobs || [];

    var cardsById = {};
    var originalOrder = [];
    listCol.querySelectorAll('.job-list-card').forEach(function (li) {
      var link = li.querySelector('.job-list-card__link');
      var href = link ? link.getAttribute('href') : '';
      var id = href ? href.split('/').pop().replace('.html', '') : null;
      if (!id) return;
      cardsById[id] = li;
      originalOrder.push(li);

      if (!li.querySelector('.job-list-card__distance')) {
        var badge = document.createElement('span');
        badge.className = 'job-list-card__distance';
        var body = li.querySelector('.job-list-card__body');
        if (body) body.insertBefore(badge, body.firstChild);
      }
    });

    var state = {
      category: new Set(),
      employment: new Set(),
      area: new Set(),
      facility: null,
      freeword: '',
      distances: null, // { [jobId]: km } while GPS active
    };

    panel.hidden = false;

    panel.querySelectorAll('.job-search-panel__chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        var group = chip.parentElement.getAttribute('data-filter-group');
        var value = chip.getAttribute('data-value');
        var set = state[group];
        var pressed = chip.getAttribute('aria-pressed') === 'true';
        chip.setAttribute('aria-pressed', String(!pressed));
        if (pressed) set.delete(value);
        else set.add(value);
        applyFilters();
      });
    });

    if (freewordEl) {
      freewordEl.addEventListener('input', function () {
        state.freeword = freewordEl.value.trim();
        applyFilters();
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        state.category.clear();
        state.employment.clear();
        state.area.clear();
        state.facility = null;
        state.freeword = '';
        state.distances = null;
        if (freewordEl) freewordEl.value = '';
        panel.querySelectorAll('.job-search-panel__chip').forEach(function (chip) {
          chip.setAttribute('aria-pressed', 'false');
        });
        root.setAttribute('data-gps-active', 'false');
        setGpsStatus('');
        restoreOriginalOrder();
        setFacilityFilter(null);
        clearHighlight();
        mapPanelsEl.querySelectorAll('.job-map-pin.is-nearest').forEach(function (p) {
          p.classList.remove('is-nearest');
        });
        applyFilters();
      });
    }

    if (facilityFilterClear) {
      facilityFilterClear.addEventListener('click', function () {
        state.facility = null;
        setFacilityFilter(null);
        clearHighlight();
        applyFilters();
      });
    }

    function restoreOriginalOrder() {
      originalOrder.forEach(function (li) {
        listCol.querySelector('.job-list__cards').appendChild(li);
      });
    }

    function clearHighlight() {
      listCol.querySelectorAll('.job-list-card.is-highlighted').forEach(function (li) {
        li.classList.remove('is-highlighted');
      });
    }

    function setFacilityFilter(key) {
      if (!facilityFilterBar) return;
      if (!key) {
        facilityFilterBar.hidden = true;
        return;
      }
      var f = facilities[key];
      if (!f) return;
      facilityFilterBar.hidden = false;
      if (facilityFilterLabel) facilityFilterLabel.textContent = f.name + ' の求人のみ表示中';
    }

    function setGpsStatus(text, isError) {
      if (!gpsStatus) return;
      if (!text) {
        gpsStatus.hidden = true;
        gpsStatus.textContent = '';
        gpsStatus.removeAttribute('data-state');
        return;
      }
      gpsStatus.hidden = false;
      gpsStatus.textContent = text;
      if (isError) gpsStatus.setAttribute('data-state', 'error');
      else gpsStatus.removeAttribute('data-state');
    }

    function matchesFilters(job) {
      if (state.category.size && !state.category.has(job.category)) return false;
      if (state.area.size && !state.area.has(job.area)) return false;
      if (state.facility && job.facilityKey !== state.facility) return false;
      if (state.employment.size) {
        var hit = job.employment.some(function (e) { return state.employment.has(e); });
        if (!hit) return false;
      }
      if (state.freeword) {
        var li = cardsById[job.id];
        var text = li ? li.textContent.toLowerCase() : '';
        if (text.indexOf(state.freeword.toLowerCase()) === -1) return false;
      }
      return true;
    }

    function applyFilters() {
      var visibleCount = 0;
      var visibleFacilityKeys = {};

      jobs.forEach(function (job) {
        var li = cardsById[job.id];
        if (!li) return;
        var visible = matchesFilters(job);
        li.hidden = !visible;
        if (visible) {
          visibleCount += 1;
          visibleFacilityKeys[job.facilityKey] = true;

          if (state.distances) {
            var badge = li.querySelector('.job-list-card__distance');
            var km = state.distances[job.facilityKey];
            if (badge && typeof km === 'number') {
              badge.textContent = '現在地から約 ' + km.toFixed(1) + ' km';
            }
          }
        }
      });

      if (state.distances) {
        var distanceOf = function (job) {
          var km = state.distances[job.facilityKey];
          return typeof km === 'number' ? km : Infinity;
        };
        var sorted = jobs
          .filter(function (job) { return cardsById[job.id] && !cardsById[job.id].hidden; })
          .sort(function (a, b) { return distanceOf(a) - distanceOf(b); });
        var ul = listCol.querySelector('.job-list__cards');
        sorted.forEach(function (job) { ul.appendChild(cardsById[job.id]); });
      }

      countEl.textContent = visibleCount + ' 件を表示中';
      if (emptyMessage) emptyMessage.hidden = visibleCount !== 0;
      updatePins(visibleFacilityKeys);
    }

    // --- 福岡・鹿児島 拡大パネル地図(2026-07-24改訂) ---
    // 第1弾(Leaflet+地理院タイル→白地図)は「実地図画像である限りトンマナと合わない」、
    // 第2弾(九州シルエット全体+県重心1点にピンを団子状集約)は「雑になった」との指摘を
    // 順に受けての改訂。拠点が実在するのは福岡・鹿児島の2県のみで、九州シルエット全体を
    // 出すと残り5県分が意味を持たないまま画面を占有してしまうため、対象2県だけを
    // assets/img/kyushu-map.svg のポリゴンから抜き出し、県ごとに拡大した個別パネルとして
    // 並べる。ピンは各拠点の実緯度経度(GPS距離計算に使っている値と同じ)を県の外接矩形
    // (kyushu-map.svg の生座標、ビルド時に一度だけ算出しハードコード)へ線形マッピングし、
    // 拠点ごとの相対位置を反映する。徒歩圏内で実質重なる拠点のみクラスタチップにまとめる。
    var AREA_ORDER = ['fukuoka', 'kagoshima'];
    var AREA_PREF = { fukuoka: '40', kagoshima: '46' };
    // 各県ポリゴンの外接矩形 (kyushu-map.svg の生座標系、他県分のポリゴンはパネル生成時に除去する)
    // 鹿児島は本土(鹿児島市周辺)の主ポリゴンのみを対象とし、遠方の離島断片は含めない
    var AREA_RAW_BBOX = {
      fukuoka: { x0: 123.0, y0: 752.0, x1: 183.0, y1: 810.0 },
      kagoshima: { x0: 118.0, y0: 861.0, x1: 176.0, y1: 935.0 },
    };
    var AREA_PAD = 0.2; // 県の外接矩形に対する外側余白(パネルのズーム・フレーミング用)
    var AREA_FACILITY_INSET = 0.15; // 拠点位置を外接矩形のどこまで寄せて配置するか(海岸線への貼り付き防止)
    // ピンは26px四方を45deg回転表示のため見た目の外接円は約37pxになる。しきい値をピン幅
    // ちょうど(30px程度)にすると回転後のバウンディングボックスが重なり、片方が完全に
    // 隠れてしまうケースが実機検証で見つかった(福岡支店ピンが博多ピンを覆い隠す等)ため、
    // 37pxに余裕を持たせた42pxをしきい値とする。
    var CLUSTER_MERGE_PX = 42;
    var CLUSTER_REF_WIDTH = 320; // %→pxの概算換算基準(1パネルあたりの想定描画幅)
    var popupEl = null;

    function areaViewBox(area) {
      var b = AREA_RAW_BBOX[area];
      var w = b.x1 - b.x0;
      var h = b.y1 - b.y0;
      return {
        x: b.x0 - w * AREA_PAD,
        y: b.y0 - h * AREA_PAD,
        w: w * (1 + 2 * AREA_PAD),
        h: h * (1 + 2 * AREA_PAD),
      };
    }

    function computeFacilityPositions() {
      var positions = {};
      AREA_ORDER.forEach(function (area) {
        var b = AREA_RAW_BBOX[area];
        var keys = Object.keys(facilities).filter(function (k) { return facilities[k].area === area; });
        if (!keys.length || !b) return;

        var lats = keys.map(function (k) { return facilities[k].lat; });
        var lngs = keys.map(function (k) { return facilities[k].lng; });
        var latMin = Math.min.apply(null, lats);
        var latMax = Math.max.apply(null, lats);
        var lngMin = Math.min.apply(null, lngs);
        var lngMax = Math.max.apply(null, lngs);

        var w = b.x1 - b.x0;
        var h = b.y1 - b.y0;
        var ix0 = b.x0 + w * AREA_FACILITY_INSET;
        var ix1 = b.x1 - w * AREA_FACILITY_INSET;
        var iy0 = b.y0 + h * AREA_FACILITY_INSET;
        var iy1 = b.y1 - h * AREA_FACILITY_INSET;
        var vb = areaViewBox(area);

        keys.forEach(function (key) {
          var f = facilities[key];
          var tx = lngMax === lngMin ? 0.5 : (f.lng - lngMin) / (lngMax - lngMin);
          var ty = latMax === latMin ? 0.5 : (latMax - f.lat) / (latMax - latMin); // 北(緯度大)が上
          var xRaw = ix0 + tx * (ix1 - ix0);
          var yRaw = iy0 + ty * (iy1 - iy0);
          positions[key] = {
            area: area,
            left: ((xRaw - vb.x) / vb.w) * 100,
            top: ((yRaw - vb.y) / vb.h) * 100,
          };
        });
      });
      return positions;
    }

    function clusterFacilityPositions(positions) {
      var refHeight = {};
      AREA_ORDER.forEach(function (area) {
        var vb = areaViewBox(area);
        refHeight[area] = CLUSTER_REF_WIDTH * (vb.h / vb.w);
      });

      var clusters = [];
      Object.keys(positions).forEach(function (key) {
        var pos = positions[key];
        var target = null;
        for (var i = 0; i < clusters.length; i++) {
          var c = clusters[i];
          if (c.area !== pos.area) continue;
          var dx = ((c.left - pos.left) / 100) * CLUSTER_REF_WIDTH;
          var dy = ((c.top - pos.top) / 100) * refHeight[pos.area];
          if (Math.sqrt(dx * dx + dy * dy) < CLUSTER_MERGE_PX) {
            target = c;
            break;
          }
        }
        if (target) target.keys.push(key);
        else clusters.push({ area: pos.area, left: pos.left, top: pos.top, keys: [key] });
      });
      return clusters;
    }

    function categoryClass(cats) {
      if (!cats || cats.length !== 1) return 'job-map-pin--mixed';
      return 'job-map-pin--' + cats[0];
    }

    function updatePins(visibleFacilityKeys) {
      mapPanelsEl.querySelectorAll('.job-map-pin').forEach(function (pin) {
        var key = pin.getAttribute('data-facility-key');
        pin.classList.toggle('is-dimmed', !visibleFacilityKeys[key]);
      });
    }

    function closePopup() {
      if (popupEl) {
        popupEl.remove();
        popupEl = null;
      }
    }

    function showPopup(key, pinEl) {
      closePopup();
      var f = facilities[key];
      if (!f) return;
      var diagramEl = diagramEls[f.area];
      if (!diagramEl) return;
      var diagramRect = diagramEl.getBoundingClientRect();
      var pinRect = pinEl.getBoundingClientRect();

      popupEl = document.createElement('div');
      popupEl.className = 'job-map-popup';
      popupEl.innerHTML =
        '<button type="button" class="job-map-popup__close" aria-label="閉じる">×</button>' +
        '<p class="job-map-popup__title">' + escapeHtml(f.name) + '</p>' +
        '<p class="job-map-popup__count">' + f.jobCount + ' 件の求人 ／ ' + escapeHtml(f.city) + '</p>' +
        '<button type="button" class="job-map-popup__link" data-facility-key="' + key + '">この拠点の求人だけ表示</button>';
      diagramEl.appendChild(popupEl);

      var left = pinRect.left - diagramRect.left + pinRect.width / 2 - popupEl.offsetWidth / 2;
      var maxLeft = diagramRect.width - popupEl.offsetWidth - 8;
      popupEl.style.left = Math.max(8, Math.min(left, maxLeft)) + 'px';

      // 下段(鹿児島エリア等)のピンでは pin の下に表示すると .job-map-wrap の
      // overflow:hidden で吹き出しが切れて見えなくなるため、下に十分な余白が
      // ない場合は pin の上側に表示する(実機検証で発覚)。
      var top = pinRect.top - diagramRect.top + pinRect.height + 8;
      var popupHeight = popupEl.offsetHeight;
      if (top + popupHeight > diagramRect.height - 8) {
        top = Math.max(8, pinRect.top - diagramRect.top - popupHeight - 8);
      }
      popupEl.style.top = top + 'px';

      popupEl.querySelector('.job-map-popup__close').addEventListener('click', closePopup);
      popupEl.querySelector('.job-map-popup__link').addEventListener('click', function () {
        state.facility = key;
        setFacilityFilter(key);
        applyFilters();
        highlightFacility(key);
        closePopup();
      });
    }

    document.addEventListener('click', function (e) {
      if (!popupEl) return;
      if (popupEl.contains(e.target) || e.target.closest('.job-map-pin')) return;
      closePopup();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closePopup();
    });

    function buildPinClusters() {
      // 拠点の実緯度経度から算出した位置をもとに、近接する拠点だけをクラスタチップへ
      // まとめ、エリアごとの拡大パネルに描画する(単独拠点はそのまま1ピンのチップになる)。
      var positions = computeFacilityPositions();
      var clusters = clusterFacilityPositions(positions);
      var clustersByArea = {};
      clusters.forEach(function (cluster) {
        (clustersByArea[cluster.area] = clustersByArea[cluster.area] || []).push(cluster);
      });

      AREA_ORDER.forEach(function (area) {
        var target = diagramEls[area];
        if (!target) return;
        var areaClusters = clustersByArea[area] || [];
        var html = areaClusters.map(function (cluster) {
          // 単独拠点は白チップで囲まず、素のピンマーカーとして直接配置する
          // (重なる拠点だけをチップにまとめる方が地図全体がすっきり見えるため)。
          if (cluster.keys.length === 1) {
            var key = cluster.keys[0];
            var f = facilities[key];
            return (
              '<button type="button" class="job-map-pin job-map-pin--solo ' + categoryClass(f.categories) + '" ' +
              'style="left:' + cluster.left + '%;top:' + cluster.top + '%" ' +
              'data-facility-key="' + key + '" aria-label="' + escapeHtml(f.name) + '"></button>'
            );
          }
          var h = '<div class="job-map-pin-cluster" style="left:' + cluster.left + '%;top:' + cluster.top + '%">';
          cluster.keys.forEach(function (key) {
            var f = facilities[key];
            h +=
              '<button type="button" class="job-map-pin ' + categoryClass(f.categories) + '" ' +
              'data-facility-key="' + key + '" aria-label="' + escapeHtml(f.name) + '"></button>';
          });
          h += '</div>';
          return h;
        }).join('');

        var wrap = document.createElement('div');
        wrap.innerHTML = html;
        Array.prototype.slice.call(wrap.children).forEach(function (cluster) {
          target.appendChild(cluster);
        });
      });

      mapPanelsEl.querySelectorAll('.job-map-pin').forEach(function (pin) {
        pin.addEventListener('click', function (e) {
          e.stopPropagation();
          var key = pin.getAttribute('data-facility-key');
          showPopup(key, pin);
          highlightFacility(key);
        });
      });

      // 地図SVGの取得は非同期のため、ピン生成が完了するより前にフィルタ操作や
      // GPSボタンのクリックが起きているケースがある(実機検証で発覚)。その間に
      // 生成された状態(絞り込み結果・現在地からの最寄り拠点)をピン生成直後に
      // 反映し直す。
      applyNearestPinHighlight();
      applyFilters();
    }

    function applyNearestPinHighlight() {
      if (!state.distances) return;
      mapPanelsEl.querySelectorAll('.job-map-pin.is-nearest').forEach(function (p) {
        p.classList.remove('is-nearest');
      });
      var nearestKey = Object.keys(state.distances).sort(function (a, b) {
        return state.distances[a] - state.distances[b];
      })[0];
      if (!nearestKey) return;
      var nearestPin = mapPanelsEl.querySelector('[data-facility-key="' + nearestKey + '"]');
      if (nearestPin) nearestPin.classList.add('is-nearest');
    }

    function buildAreaSvgMarkup(svgText, area) {
      var wrap = document.createElement('div');
      wrap.innerHTML = svgText;
      var svg = wrap.querySelector('svg');
      var prefCode = AREA_PREF[area];
      svg.querySelectorAll('[data-pref]').forEach(function (el) {
        if (el.getAttribute('data-pref') !== prefCode) el.remove();
      });
      var vb = areaViewBox(area);
      svg.setAttribute('viewBox', vb.x + ' ' + vb.y + ' ' + vb.w + ' ' + vb.h);
      return svg.outerHTML;
    }

    function initDiagram() {
      fetch('assets/img/kyushu-map.svg')
        .then(function (res) {
          if (!res.ok) throw new Error('kyushu-map.svg fetch failed: ' + res.status);
          return res.text();
        })
        .then(function (svgText) {
          AREA_ORDER.forEach(function (area) {
            var target = diagramEls[area];
            if (!target) return;
            target.innerHTML = buildAreaSvgMarkup(svgText, area);
          });
          buildPinClusters();
          mapWrap.hidden = false;
        })
        .catch(function () {
          // 地図画像の取得・描画に失敗した場合は非表示のまま(フィルタ・求人一覧は影響を受けない)。
        });
    }

    function highlightFacility(key) {
      clearHighlight();
      var firstMatch = null;
      jobs.forEach(function (job) {
        if (job.facilityKey !== key) return;
        var li = cardsById[job.id];
        if (!li || li.hidden) return;
        li.classList.add('is-highlighted');
        if (!firstMatch) firstMatch = li;
      });
      if (firstMatch) {
        firstMatch.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
      }
    }

    function escapeHtml(str) {
      return String(str).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    }

    // --- GPS ---
    if (gpsBtn) {
      gpsBtn.addEventListener('click', function () {
        if (!('geolocation' in navigator)) {
          setGpsStatus('この端末・ブラウザは現在地取得に対応していません。', true);
          return;
        }
        gpsBtn.disabled = true;
        setGpsStatus('現在地を取得しています…');

        navigator.geolocation.getCurrentPosition(
          function (pos) {
            var lat = pos.coords.latitude;
            var lng = pos.coords.longitude;
            var distances = {};
            Object.keys(facilities).forEach(function (key) {
              var f = facilities[key];
              distances[key] = haversineKm(lat, lng, f.lat, f.lng);
            });
            state.distances = distances;
            root.setAttribute('data-gps-active', 'true');
            setGpsStatus('現在地から近い順に並び替えました。');
            gpsBtn.disabled = false;

            applyNearestPinHighlight();
            applyFilters();
          },
          function (err) {
            gpsBtn.disabled = false;
            if (err.code === err.PERMISSION_DENIED) {
              setGpsStatus('位置情報の利用が許可されませんでした。ブラウザの設定をご確認ください。', true);
            } else if (err.code === err.TIMEOUT) {
              setGpsStatus('現在地の取得がタイムアウトしました。もう一度お試しください。', true);
            } else {
              setGpsStatus('現在地を取得できませんでした。', true);
            }
          },
          { timeout: 8000 }
        );
      });
    }

    initDiagram();
    applyFilters();
  }
})();
