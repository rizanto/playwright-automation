import time
import random
import math

# Global mouse position tracker per page
_mouse_positions = {}

def get_current_mouse_pos(page):
    """Mendapatkan posisi mouse saat ini atau default ke kuadran tengah layar."""
    page_id = id(page)
    if page_id not in _mouse_positions:
        _mouse_positions[page_id] = (random.randint(400, 600), random.randint(300, 500))
    return _mouse_positions[page_id]

def set_current_mouse_pos(page, x, y):
    """Memperbarui posisi mouse terkini."""
    page_id = id(page)
    _mouse_positions[page_id] = (x, y)

def _cubic_bezier(p0, p1, p2, p3, t):
    """Menghitung koordinat kurva Cubic Bezier pada nilai t (0..1)."""
    return (
        (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0],
        (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
    )

def human_move_to(page, target_x, target_y, steps=None):
    """
    Menggerakkan kursor mouse dari posisi saat ini ke target (target_x, target_y) 
    menggunakan lintasan Kurva Bezier lengkung alami khas manusia dengan variasi kecepatan.
    """
    start_x, start_y = get_current_mouse_pos(page)
    
    distance = math.hypot(target_x - start_x, target_y - start_y)
    if distance < 3:
        set_current_mouse_pos(page, target_x, target_y)
        return

    if steps is None:
        steps = max(12, int(distance / 25) + random.randint(3, 8))

    # Tentukan 2 titik kontrol lengkungan kurva secara acak
    ctrl_offset_x = (target_x - start_x) * random.uniform(0.2, 0.8) + random.uniform(-60, 60)
    ctrl_offset_y = (target_y - start_y) * random.uniform(0.2, 0.8) + random.uniform(-60, 60)
    
    p0 = (start_x, start_y)
    p1 = (start_x + ctrl_offset_x, start_y + random.uniform(-40, 40))
    p2 = (start_x + ctrl_offset_x, start_y + ctrl_offset_y)
    p3 = (target_x, target_y)

    for i in range(1, steps + 1):
        t = i / steps
        # Easing function (ease-out) agar gerakan melambat mendekati target
        t_eased = 1 - (1 - t) ** 2
        
        curr_x, curr_y = _cubic_bezier(p0, p1, p2, p3, t_eased)
        
        # Tambahkan jitter mikro acak kecil (+- 1px)
        if i < steps:
            curr_x += random.uniform(-1.0, 1.0)
            curr_y += random.uniform(-1.0, 1.0)
            
        page.mouse.move(curr_x, curr_y)
        set_current_mouse_pos(page, curr_x, curr_y)
        
        # Jeda waktu mikro variabel per step
        sleep_step = random.uniform(0.005, 0.018)
        time.sleep(sleep_step)

    # Pastikan kursor benar-benar mendarat di koordinat target
    page.mouse.move(target_x, target_y)
    set_current_mouse_pos(page, target_x, target_y)

def human_click(page, locator_or_selector, force_scroll=True, click_hold_ms=None):
    """
    Menemukan elemen target, menggerakkan kursor mouse secara alami ke dalam area elemen tersebut, 
    memberikan jeda manusiawi, dan melakukan klik (press & release).
    """
    if isinstance(locator_or_selector, str):
        loc = page.locator(locator_or_selector).first
    else:
        loc = locator_or_selector

    if force_scroll:
        try:
            loc.scroll_into_view_if_needed(timeout=5000)
            time.sleep(random.uniform(0.1, 0.25))
        except: pass

    box = loc.bounding_box()
    if not box:
        # Fallback jika bounding_box gagal didapat
        loc.click(force=True)
        return True

    # Hitung posisi klik acak di dalam area elemen (bukan pas di tengah mati)
    padding_x = box['width'] * random.uniform(0.25, 0.75)
    padding_y = box['height'] * random.uniform(0.25, 0.75)
    target_x = box['x'] + padding_x
    target_y = box['y'] + padding_y

    # 1. Gerakkan mouse secara alami ke elemen
    human_move_to(page, target_x, target_y)
    
    # 2. Jeda ragu manusiawi (hesitation) sebelum menekan tombol mouse
    time.sleep(random.uniform(0.08, 0.22))

    # 3. Tekan dan lepaskan tombol mouse (mouse down -> delay -> mouse up)
    page.mouse.down()
    hold_delay = (click_hold_ms / 1000.0) if click_hold_ms else random.uniform(0.04, 0.11)
    time.sleep(hold_delay)
    page.mouse.up()
    
    # 4. Jeda pasca-klik
    time.sleep(random.uniform(0.12, 0.30))
    return True

def human_type(page, locator_or_selector, text, clear_first=False):
    """
    Mengklik elemen input secara alami, lalu mengetik teks karakter demi karakter 
    dengan variasi ritme ketikan keyboard manusia.
    """
    human_click(page, locator_or_selector)
    
    if clear_first:
        page.keyboard.press("Control+A")
        time.sleep(random.uniform(0.05, 0.12))
        page.keyboard.press("Backspace")
        time.sleep(random.uniform(0.1, 0.25))

    for char in text:
        page.keyboard.type(char)
        
        # Variasi jeda antar karakter (simulasi manusia)
        if char in " .@_-":
            delay = random.uniform(0.12, 0.28) # Jeda lebih panjang untuk spasi & simbol
        else:
            delay = random.uniform(0.04, 0.14) # Ketikan huruf biasa
            
        time.sleep(delay)
        
    time.sleep(random.uniform(0.15, 0.35))

def human_scroll(page, direction="down", amount=300):
    """Menggulirkan layar (scroll) secara bertahap menggunakan scroll wheel mouse."""
    steps = random.randint(3, 6)
    delta_per_step = (amount if direction == "down" else -amount) / steps
    
    for _ in range(steps):
        step_delta = delta_per_step + random.uniform(-15, 15)
        page.mouse.wheel(0, step_delta)
        time.sleep(random.uniform(0.08, 0.18))
    time.sleep(random.uniform(0.2, 0.4))
