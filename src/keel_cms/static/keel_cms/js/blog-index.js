/*
 * keel-cms · Blog Index behavior.
 *
 * Powers the slider + live variants of the Blog Index Template design library.
 * Vanilla, dependency-free, no inline handlers: it reads data-* hooks, pauses
 * autoplay on hover, and honors prefers-reduced-motion (all animation is opt-in
 * and skipped when the user asked for reduced motion). Seed content renders with
 * JS disabled; this only enhances. Load it only when a chosen variant is marked
 * data-keel-requires-js="true":
 *   <script src="{% static 'keel_cms/js/blog-index.js' %}" defer></script>
 */
(function(){
  "use strict";
  var mq = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  var reduce = !!(mq && mq.matches);
  function $(s,c){ return (c||document).querySelector(s); }
  function $all(s,c){ return Array.prototype.slice.call((c||document).querySelectorAll(s)); }

  /* Card carousels: header prev/next paginate by the number of visible cards. */
  $all('[data-carousel]').forEach(function(root){
    var track = $('[data-carousel-track]', root); if(!track) return;
    var prev = $('[data-carousel-prev]', root), next = $('[data-carousel-next]', root);
    function page(){
      var first = track.firstElementChild;
      var gap = parseFloat(getComputedStyle(track).columnGap) || 16;
      var cw = first ? first.getBoundingClientRect().width + gap : track.clientWidth;
      var per = Math.max(1, Math.round(track.clientWidth / cw));
      return cw * per;
    }
    function update(){
      if(prev) prev.disabled = track.scrollLeft <= 4;
      if(next) next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 4;
    }
    if(next) next.addEventListener('click', function(){ track.scrollBy({left: page(), behavior:'smooth'}); });
    if(prev) prev.addEventListener('click', function(){ track.scrollBy({left: -page(), behavior:'smooth'}); });
    track.addEventListener('scroll', update, {passive:true});
    window.addEventListener('resize', update);
    update();
  });

  /* Fade rotators: generated dots, pre-authored thumbnails, arrows, hover-pausing autoplay. */
  $all('[data-slider]').forEach(function(root){
    var slides = $all('[data-slide]', root); if(!slides.length) return;
    var dotsWrap = $('[data-slider-dots]', root);
    var thumbs = $all('[data-ts-thumb]', root);
    var i = slides.findIndex(function(s){ return s.classList.contains('is-active'); });
    if(i < 0) i = 0;
    var dots = [];
    if(dotsWrap){
      slides.forEach(function(_, idx){
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'slider-dot';
        b.setAttribute('aria-label', 'Show slide ' + (idx+1));
        b.addEventListener('click', function(){ go(idx, true); });
        dotsWrap.appendChild(b); dots.push(b);
      });
    }
    thumbs.forEach(function(t, idx){ t.addEventListener('click', function(){ go(idx, true); }); });
    function go(n, user){
      slides[i].classList.remove('is-active');
      if(dots[i]) dots[i].classList.remove('is-active');
      if(thumbs[i]) thumbs[i].classList.remove('is-active');
      i = (n + slides.length) % slides.length;
      slides[i].classList.add('is-active');
      if(dots[i]) dots[i].classList.add('is-active');
      if(thumbs[i]) thumbs[i].classList.add('is-active');
      if(user) restart();
    }
    var np = $('[data-slider-next]', root), pv = $('[data-slider-prev]', root);
    if(np) np.addEventListener('click', function(){ go(i+1, true); });
    if(pv) pv.addEventListener('click', function(){ go(i-1, true); });
    go(i, false);
    var raw = root.getAttribute('data-slider');
    var delay = (raw === null || raw === '') ? 5000 : parseInt(raw, 10);
    var timer = null;
    function restart(){
      if(timer) clearInterval(timer);
      if(reduce || !delay || delay <= 0) return;
      timer = setInterval(function(){ go(i+1, false); }, delay);
    }
    root.addEventListener('mouseenter', function(){ if(timer) clearInterval(timer); });
    root.addEventListener('mouseleave', restart);
    restart();
  });

  /* Build a live item from a <template> + a data object. */
  function build(tpl, d){
    var node = tpl.content.firstElementChild.cloneNode(true);
    $all('[data-field]', node).forEach(function(el){
      var f = el.getAttribute('data-field');
      if(f === 'img'){ el.setAttribute('src', d.img); el.setAttribute('alt', d.title || ''); }
      else if(f === 'chip'){ el.textContent = d.chip; el.className = 'chip ' + (d.chipClass || ''); }
      else { el.textContent = (d[f] != null) ? d[f] : ''; }
    });
    return node;
  }
  function poolOf(root){
    var el = $('[data-live-pool]', root); if(!el) return [];
    try { return JSON.parse(el.textContent); } catch(e){ return []; }
  }

  /* Auto-updating feeds: prepend a fresh item, fade the oldest out. */
  $all('[data-live-feed]').forEach(function(root){
    var list = $('[data-live-list]', root), tpl = $('[data-live-template]', root);
    var pool = poolOf(root);
    if(!list || !tpl || !pool.length || reduce) return;
    var max = parseInt(root.getAttribute('data-live-max'), 10) || 6;
    var delay = parseInt(root.getAttribute('data-live-feed'), 10) || 3500;
    var k = 0;
    setInterval(function(){
      var node = build(tpl, pool[k % pool.length]); k++;
      node.classList.add('flash-in');
      list.insertBefore(node, list.firstChild);
      if(list.children.length > max){
        var last = list.lastElementChild;
        last.classList.add('fade-out');
        (function(el){ setTimeout(function(){ if(el.parentNode) el.parentNode.removeChild(el); }, 520); })(last);
        while(list.children.length > max + 1){ list.removeChild(list.lastElementChild); }
      }
    }, delay);
  });

  /* Live blog: a visible countdown; at zero, post a new entry to the top. */
  $all('[data-liveblog]').forEach(function(root){
    var list = $('[data-live-list]', root), tpl = $('[data-live-template]', root), cd = $('[data-countdown]', root);
    var pool = poolOf(root);
    if(!list || !tpl || !pool.length || reduce) return;
    var period = Math.max(3, Math.round((parseInt(root.getAttribute('data-liveblog'), 10) || 12000) / 1000));
    var max = parseInt(root.getAttribute('data-live-max'), 10) || 7;
    var t = period, k = 0;
    if(cd) cd.textContent = t;
    setInterval(function(){
      t--;
      if(cd) cd.textContent = (t < 0 ? 0 : t);
      if(t <= 0){
        var node = build(tpl, pool[k % pool.length]); k++;
        node.classList.add('flash-in');
        list.insertBefore(node, list.firstChild);
        while(list.children.length > max){ list.removeChild(list.lastElementChild); }
        t = period;
      }
    }, 1000);
  });

  /* Ticking counters. */
  $all('[data-count]').forEach(function(el){
    if(reduce) return;
    var cur = parseInt(el.getAttribute('data-count'), 10) || 0;
    var step = parseInt(el.getAttribute('data-count-step'), 10) || 5;
    setInterval(function(){
      cur += Math.floor(Math.random() * step) + 1;
      el.textContent = cur.toLocaleString('en-US');
    }, 2200);
  });

  /* Curriculum progress bar: fill = completed / total lessons. */
  $all('[data-progress]').forEach(function(bar){
    var box = bar.closest('.curriculum');
    if(!box){ bar.style.width = '40%'; return; }
    var total = $all('.lesson', box).length, done = $all('.lesson--done', box).length;
    bar.style.width = total ? Math.round(done / total * 100) + '%' : '0%';
  });
})();
