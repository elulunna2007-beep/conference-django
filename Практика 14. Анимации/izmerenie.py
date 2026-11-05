"""Замер скорости страниц с анимациями и без них. Запуск: python izmerenie.py (портал должен работать на порту 8101)."""
import statistics
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE = "http://127.0.0.1:8101"
PAGES = ["/", "/events/"]
RUNS = 7
NO_ANIM = "* , *::before, *::after { animation: none !important; transition: none !important; }"

# LCP и CLS собираем наблюдателем, кадры считаем через requestAnimationFrame первую секунду после загрузки
JS = """
const done = arguments[arguments.length - 1];
let lcp = 0, cls = 0, frames = 0;
new PerformanceObserver(l => { for (const e of l.getEntries()) lcp = e.startTime; }).observe({type: 'largest-contentful-paint', buffered: true});
new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; }).observe({type: 'layout-shift', buffered: true});
const t0 = performance.now();
function tick() { frames++; if (performance.now() - t0 < 1000) requestAnimationFrame(tick); else done({lcp: lcp, cls: cls, fps: frames}); }
requestAnimationFrame(tick);
"""


def driver():
    o = Options()
    o.add_argument("--headless=new")
    o.add_argument("--window-size=1280,800")
    o.add_argument("--lang=ru")
    d = webdriver.Chrome(options=o)
    d.set_script_timeout(10)
    return d


def measure(path, animations):
    res = []
    for _ in range(RUNS):
        d = driver()
        try:
            if not animations:
                d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source":
                    "document.addEventListener('DOMContentLoaded', () => { const s = document.createElement('style'); s.textContent = '%s'; document.head.appendChild(s); });" % NO_ANIM})
            d.get(BASE + path)
            res.append(d.execute_async_script(JS))
        finally:
            d.quit()
    return res


def check_transition():
    """Переход между страницами: событие pagereveal сообщает, что браузер запустил view transition."""
    d = driver()
    try:
        d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source":
            "addEventListener('pagereveal', e => sessionStorage.setItem('vt', e.viewTransition ? 'есть' : 'нет'));"})
        d.get(BASE + "/")
        d.find_element("link text", "Мероприятия").click()
        time.sleep(1)
        return d.current_url, d.execute_script("return sessionStorage.getItem('vt')")
    finally:
        d.quit()


def check_reduced():
    d = driver()
    try:
        d.execute_cdp_cmd("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
        d.get(BASE + "/events/")
        return d.execute_script("return getComputedStyle(document.querySelector('.card')).animationName")
    finally:
        d.quit()


if __name__ == "__main__":
    print("Замер, %d запусков на страницу, медиана" % RUNS)
    print("%-10s %-14s %8s %8s %6s" % ("страница", "режим", "LCP, мс", "CLS", "кадры"))
    for p in PAGES:
        for anim in (False, True):
            r = measure(p, anim)
            print("%-10s %-14s %8.0f %8.3f %6.0f" % (p, "с анимациями" if anim else "без анимаций",
                  statistics.median(x["lcp"] for x in r), statistics.median(x["cls"] for x in r), statistics.median(x["fps"] for x in r)))
    print("Переход между страницами, view transition:", check_transition())
    print("С включённым «уменьшить анимацию» у карточки animation-name =", check_reduced())
