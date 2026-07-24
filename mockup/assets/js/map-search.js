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

  // エリア(福岡/鹿児島)ごとに独立したGoogle Mapsパネルを表示するため、
  // 地図の描画先はエリア別の複数要素になる。
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
        applyNearestMarkerHighlight();
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
      updateMarkers(visibleFacilityKeys);
    }

    // --- Google Maps 埋め込み(2026-07-24) ---
    // 実地図(Leaflet+地理院タイル) → 抽象ブロブ図 → 九州シルエットSVG(県重心1点→拠点別
    // 拡大2パネル)と決裁者フィードバックを受けて刷新を重ねた末、「理想はGoogleマップで
    // 対応できないか」との明示指示によりGoogle Maps JavaScript APIの実地図埋め込みへ
    // 最終的に刷新(過去の「実地図はトンマナと合わない」という却下判断を、この指示に
    // 基づき明示的に上書きする形で再度実地図を採用)。福岡/鹿児島の2エリアはそれぞれ
    // 独立したgoogle.maps.Mapインスタンスとして拡大表示し、各拠点の実緯度経度に
    // fitBoundsで自動フィットする。ピンは既存の職種カテゴリ配色を再現したカスタム
    // アイコン(白縁取り、地図の色と衝突しないよう)。POI/交通機関/道路ラベルは
    // styles配列で非表示にしブランドカラーに寄せることで、雑多な実地図情報を削ぎ落とし
    // つつスタイリッシュな見た目に近づける。実地図はユーザー自身がズーム操作できるため、
    // 過去バージョンで実装していた近接拠点の独自クラスタリングロジックは不要になった。
    var AREA_ORDER = ['fukuoka', 'kagoshima'];
    var CATEGORY_COLOR = {
      care: '#0a52b8',
      nurse: '#1f7a6a',
      office: '#b06a1f',
      it: '#5a3ea8',
    };
    var MIXED_COLOR = '#6b7280';
    var CUSTOM_MAP_STYLE = [
      { elementType: 'geometry', stylers: [{ color: '#f8f5ee' }] },
      { elementType: 'labels.icon', stylers: [{ visibility: 'off' }] },
      { elementType: 'labels.text.fill', stylers: [{ color: '#575656' }] },
      { elementType: 'labels.text.stroke', stylers: [{ color: '#ffffff' }] },
      { featureType: 'administrative', elementType: 'geometry.stroke', stylers: [{ color: '#d9e8fd' }] },
      { featureType: 'poi', stylers: [{ visibility: 'off' }] },
      { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#ffffff' }] },
      { featureType: 'road', elementType: 'labels', stylers: [{ visibility: 'off' }] },
      { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#d9e8fd' }] },
      { featureType: 'transit', stylers: [{ visibility: 'off' }] },
      { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#d9e8fd' }] },
    ];

    var maps = {}; // area -> google.maps.Map
    var markers = {}; // facilityKey -> google.maps.Marker
    var infoWindow = null;
    var nearestMarkerKey = null;

    function categoryColor(cats) {
      if (!cats || cats.length !== 1) return MIXED_COLOR;
      return CATEGORY_COLOR[cats[0]] || MIXED_COLOR;
    }

    function pinIconUrl(color) {
      var svg =
        '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="40" viewBox="0 0 30 40">' +
        '<path d="M15 0C6.7 0 0 6.7 0 15c0 11.3 15 25 15 25s15-13.7 15-25C30 6.7 23.3 0 15 0z" fill="' + color + '" stroke="#fff" stroke-width="2"/>' +
        '<circle cx="15" cy="15" r="6" fill="#fff"/></svg>';
      return 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg);
    }

    function markerIcon(color, isNearest) {
      var scale = isNearest ? 1.3 : 1;
      return {
        url: pinIconUrl(color),
        scaledSize: new google.maps.Size(30 * scale, 40 * scale),
        anchor: new google.maps.Point(15 * scale, 40 * scale),
      };
    }

    function closeInfoWindow() {
      if (infoWindow) infoWindow.close();
    }

    function showInfoWindow(key, marker) {
      var f = facilities[key];
      if (!f) return;
      if (!infoWindow) infoWindow = new google.maps.InfoWindow();

      var content = document.createElement('div');
      content.className = 'job-map-popup';
      content.innerHTML =
        '<p class="job-map-popup__title">' + escapeHtml(f.name) + '</p>' +
        '<p class="job-map-popup__count">' + f.jobCount + ' 件の求人 ／ ' + escapeHtml(f.city) + '</p>' +
        '<button type="button" class="job-map-popup__link">この拠点の求人だけ表示</button>';
      content.querySelector('.job-map-popup__link').addEventListener('click', function () {
        state.facility = key;
        setFacilityFilter(key);
        applyFilters();
        highlightFacility(key);
        closeInfoWindow();
      });

      infoWindow.setContent(content);
      infoWindow.open({ map: marker.getMap(), anchor: marker });
    }

    function updateMarkers(visibleFacilityKeys) {
      Object.keys(markers).forEach(function (key) {
        markers[key].setOpacity(visibleFacilityKeys[key] ? 1 : 0.3);
      });
    }

    function applyNearestMarkerHighlight() {
      if (nearestMarkerKey && markers[nearestMarkerKey]) {
        var prev = facilities[nearestMarkerKey];
        markers[nearestMarkerKey].setIcon(markerIcon(categoryColor(prev.categories), false));
        markers[nearestMarkerKey].setZIndex(null);
      }
      nearestMarkerKey = null;
      if (!state.distances) return;

      var nearestKey = Object.keys(state.distances).sort(function (a, b) {
        return state.distances[a] - state.distances[b];
      })[0];
      if (!nearestKey || !markers[nearestKey]) return;

      nearestMarkerKey = nearestKey;
      markers[nearestKey].setIcon(markerIcon(categoryColor(facilities[nearestKey].categories), true));
      markers[nearestKey].setZIndex(999);
    }

    async function initMaps() {
      try {
        await google.maps.importLibrary('maps');
      } catch (e) {
        // 地図の読み込みに失敗した場合は非表示のまま(フィルタ・求人一覧は影響を受けない)。
        return;
      }

      // fitBounds は描画先要素が実サイズを持っている必要があるため、
      // Mapインスタンス生成前に hidden を解除する。
      mapWrap.hidden = false;

      AREA_ORDER.forEach(function (area) {
        var target = diagramEls[area];
        if (!target) return;
        var keys = Object.keys(facilities).filter(function (k) { return facilities[k].area === area; });
        if (!keys.length) return;

        var bounds = new google.maps.LatLngBounds();
        keys.forEach(function (k) {
          bounds.extend({ lat: facilities[k].lat, lng: facilities[k].lng });
        });

        var map = new google.maps.Map(target, {
          styles: CUSTOM_MAP_STYLE,
          disableDefaultUI: true,
          zoomControl: true,
        });
        map.fitBounds(bounds, 48);
        // 拠点同士が近く自動フィットで過剰にズームインするケースの保険(実質1点扱いになる場合等)。
        google.maps.event.addListenerOnce(map, 'bounds_changed', function () {
          if (map.getZoom() > 15) map.setZoom(15);
        });
        maps[area] = map;

        keys.forEach(function (key) {
          var f = facilities[key];
          var marker = new google.maps.Marker({
            position: { lat: f.lat, lng: f.lng },
            map: map,
            icon: markerIcon(categoryColor(f.categories), false),
            title: f.name,
          });
          marker.addListener('click', function () {
            showInfoWindow(key, marker);
            highlightFacility(key);
          });
          markers[key] = marker;
        });
      });

      applyNearestMarkerHighlight();
      applyFilters();
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

            applyNearestMarkerHighlight();
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

    initMaps();
    applyFilters();
  }
})();
