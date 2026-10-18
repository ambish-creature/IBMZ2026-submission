"""
Fact-check app: desktop UI component (CustomTkinter, modern look, selectable themes).

Two screens, one window:
    1. INPUT  - the user pastes a tweet link and presses Check
                (a theme picker sits in the top-right corner)
    2. RESULT - tweet preview, verdict, confidence, summary, method

What this file owns
    - The window, both screens, moving between them, and the colour themes
What it does NOT own (other team members' parts)
    - Fetching a tweet from a URL                    -> fetch_tweet()
    - Claim extraction, search, verdict logic        -> check_claim()

How to plug in the other components
    Create backend.py next to this file and define either function.
    This file imports them if they exist and falls back to mocks otherwise,
    so the UI always runs.

Contract for fetch_tweet(url: str) -> dict
    {"author": str, "text": str}       # raise ValueError("friendly message") on failure

Contract for check_claim(tweet_text: str) -> dict
    {
      "claim":      str,               # the claim that was extracted
      "verdict":    str,               # key of VERDICTS below
      "confidence": float,             # 0.0 - 1.0
      "summary":    str,               # 1-2 plain-language sentences
      "method":     str,               # short "how we checked this" (optional)
    }
    Any extra keys (e.g. evidence lists) are ignored by this UI.

Theme design rules (see THEME_SPECS and build_theme)
    - Any palette colour can be the page background. Themes come in three kinds:
      light (tinted near-white), dark (a dark palette colour, light text) and
      neutral (a mid-tone palette colour, dark text).
    - Verdict colours are FIXED and never change with the theme, so "False"
      always looks like "False". Verdicts also always carry an icon + text label,
      and verdict cards keep their own pale tint and dark text in every theme.
    - Buttons use a high-contrast palette colour (darkest on light/neutral
      themes, lightest on dark themes). Bright hues are never used for buttons,
      so an accent can't be mistaken for a verdict colour.
    - Muted text is automatically nudged until it reaches 4.5:1 contrast on both
      the page and the cards.

Setup and run:
    pip install customtkinter
    python ui_desktop.py
"""

import json
import queue
import re
import sys
import threading
from pathlib import Path

try:
    import customtkinter as ctk
except ImportError:
    sys.exit("This UI needs CustomTkinter. Install it with:  pip install customtkinter")

# --------------------------------------------------------------------------
# Plug-in points (use the team's real functions if backend.py provides them)
# --------------------------------------------------------------------------

try:
    import backend as _backend
except ImportError:
    _backend = None

# Fixed verdict colours (independent of the theme)
VERDICTS = {
    "true":         {"label": "True",         "icon": "✓", "color": "#0F766E", "bg": "#E3F3F1"},
    "mostly_true":  {"label": "Mostly true",  "icon": "✓", "color": "#4D7C0F", "bg": "#EEF5E0"},
    "mixed":        {"label": "Mixed",        "icon": "≈", "color": "#A16207", "bg": "#FDF2D8"},
    "misleading":   {"label": "Misleading",   "icon": "!", "color": "#C2410C", "bg": "#FDEADB"},
    "false":        {"label": "False",        "icon": "✕", "color": "#B91C1C", "bg": "#FDE7E7"},
    "unverifiable": {"label": "Unverifiable", "icon": "?", "color": "#475467", "bg": "#EDEFF3"},
}


def _mock_fetch_tweet(url: str) -> dict:
    """Placeholder so the UI runs before the backend exists."""
    if "reef" in url.lower():
        return {"author": "@example_user",
                "text": "The Great Barrier Reef is the largest coral reef system in the world."}
    return {"author": "@example_user",
            "text": "Scientists have confirmed that drinking lemon water cures all infections."}


def _mock_check_claim(tweet_text: str) -> dict:
    import time
    time.sleep(1.2)  # pretend to work so the loading state is visible
    text = tweet_text.lower()
    if "cures all" in text:
        return {
            "claim": "Lemon water cures all infections",
            "verdict": "false",
            "confidence": 0.9,
            "summary": "No reliable evidence supports this; infections need specific treatments.",
            "method": "Extracted one claim, searched medical and fact-check sources, compared findings.",
        }
    if "great barrier reef" in text:
        return {
            "claim": "The Great Barrier Reef is the largest coral reef system in the world",
            "verdict": "mostly_true",
            "confidence": 0.85,
            "summary": "Widely documented as the largest, though exact measures vary by source.",
            "method": "Extracted one claim, checked encyclopedic and scientific sources.",
        }
    return {
        "claim": tweet_text[:120],
        "verdict": "unverifiable",
        "confidence": 0.3,
        "summary": "Not enough reliable evidence found to rate this claim.",
        "method": "Extracted claim and searched, but found no sufficient sources.",
    }


fetch_tweet = getattr(_backend, "fetch_tweet", _mock_fetch_tweet)
check_claim = getattr(_backend, "check_claim", _mock_check_claim)

# --------------------------------------------------------------------------
# Colour helpers and themes
# --------------------------------------------------------------------------


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*[max(0, min(255, round(v))) for v in rgb])


def mix(a, b, t):
    """Blend colour a toward colour b by t (0 = a, 1 = b)."""
    return _hex([x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))])


def luminance(h):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def ensure_contrast(fg, bg, minimum=4.5):
    """Nudge fg away from bg (toward black or white) until it reaches the minimum contrast."""
    target = "#000000" if contrast("#000000", bg) >= contrast("#FFFFFF", bg) else "#FFFFFF"
    for _ in range(40):
        if contrast(fg, bg) >= minimum:
            break
        fg = mix(fg, target, 0.08)
    return fg


# Four-colour palettes (as supplied by the team)
PALETTES = {
    "Blue":          ("#6A89A7", "#BDDDFC", "#88BDF2", "#384959"),
    "Slate & Cream": ("#4A4A4A", "#CBCBCB", "#FFFFE3", "#6D8196"),
    "Teal":          ("#B8E3E9", "#93B1B5", "#4F7C82", "#0B2E33"),
    "Sand":          ("#CBBD93", "#FAE8B4", "#80775C", "#574A24"),
    "Mocha":         ("#D6B588", "#C6C0B9", "#705E46", "#422701"),
}

# A theme = a palette + how to use it. Any palette colour can be the page
# background; `mode` decides how the other roles are derived:
#   light   - a very light tint of the palette's lightest colour as background
#   dark    - `base` (a dark palette colour) as background, light text
#   neutral - `base` (a mid-tone palette colour) as background, dark text
# Order here is the order in the picker. The first theme is the default.
THEME_SPECS = [
    # (name,             palette,         mode,      base)
    ("Blue",             "Blue",          "light",   None),
    ("Blue (dark)",      "Blue",          "dark",    "#384959"),
    ("Teal",             "Teal",          "light",   None),
    ("Teal (dark)",      "Teal",          "dark",    "#0B2E33"),
    ("Slate & Cream",    "Slate & Cream", "light",   None),
    ("Mocha",  "Mocha",         "neutral", "#D6B588"),
    ("Stone",  "Mocha",         "neutral", "#C6C0B9"),
    ("Sand",   "Sand",          "neutral", "#CBBD93"),
]
DEFAULT_THEME = THEME_SPECS[0][0]
WHITE = "#FFFFFF"


def build_theme(palette, mode="light", base=None):
    """Turn a 4-colour palette into named UI roles."""
    dark, _mid_dark, mid_light, light = sorted(palette, key=luminance)

    if mode == "dark":
        bg = base or dark
        card = mix(bg, WHITE, 0.08)
        text = mix(light, WHITE, 0.75)
        accent, accent_text = light, dark
        accent_hover = mix(accent, WHITE, 0.25)
        border = mix(bg, WHITE, 0.20)
        soft = mix(bg, WHITE, 0.12)
    elif mode == "neutral":
        bg = base
        card = mix(bg, WHITE, 0.75)
        text = dark
        accent, accent_text = dark, WHITE
        accent_hover = mix(dark, WHITE, 0.20)
        border = mix(bg, dark, 0.22)
        soft = mix(bg, WHITE, 0.40)
    else:  # light
        bg = mix(light, WHITE, 0.80)
        card = WHITE
        text = dark
        accent, accent_text = dark, WHITE
        accent_hover = mix(dark, WHITE, 0.20)
        border = mix(light, mid_light, 0.25)
        soft = mix(light, WHITE, 0.50)

    muted = ensure_contrast(mix(text, bg, 0.30), bg)
    muted = ensure_contrast(muted, card)          # must also read on cards
    accent_text = ensure_contrast(accent_text, accent)

    return {
        "mode": mode,
        "bg": bg,                       # page background
        "card": card,                   # cards, input field
        "text": text,                   # main text
        "muted": muted,                 # secondary text
        "accent": accent,               # buttons, progress bar
        "accent_hover": accent_hover,
        "accent_text": accent_text,     # text on buttons
        "border": border,
        "soft": soft,                   # ghost-button hover
        "scroll": mix(bg, text, 0.30),
        "scroll_hover": mix(bg, text, 0.50),
        "swatches": list(palette),
    }


THEMES = {name: build_theme(PALETTES[pal], mode, base) for name, pal, mode, base in THEME_SPECS}

SETTINGS_FILE = Path.home() / ".factcheck_ui_settings.json"


def load_theme_name():
    try:
        name = json.loads(SETTINGS_FILE.read_text()).get("theme", DEFAULT_THEME)
        return name if name in THEMES else DEFAULT_THEME
    except Exception:
        return DEFAULT_THEME


def save_theme_name(name):
    try:
        SETTINGS_FILE.write_text(json.dumps({"theme": name}))
    except Exception:
        pass  # saving the preference is optional


# --------------------------------------------------------------------------
# Layout constants and input validation
# --------------------------------------------------------------------------

ERROR = "#B42318"
CONTENT_WIDTH = 640          # width of the result column
WRAP = CONTENT_WIDTH - 80    # text wrap inside cards

TWEET_URL = re.compile(r"^https?://(www\.|mobile\.)?(x|twitter)\.com/[^/\s]+/status/\d+", re.IGNORECASE)


def is_tweet_url(url: str) -> bool:
    return bool(TWEET_URL.match(url.strip()))


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------


class FactCheckApp(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title("Fact-check")
        self.geometry("960x720")
        self.minsize(780, 580)

        self.jobs = queue.Queue()
        self.busy = False
        self.container = None
        self.result_body = None
        self.theme_name = load_theme_name()
        self.c = THEMES[self.theme_name]

        self._build_ui()

    # ---- (re)building everything for the current theme --------------------

    def _build_ui(self, keep_url=""):
        if self.container is not None:
            self.container.destroy()
        self.result_body = None
        self.configure(fg_color=self.c["bg"])

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.input_screen = self._build_input_screen(self.container)
        self.result_screen = self._build_result_screen(self.container)
        for screen in (self.input_screen, self.result_screen):
            screen.grid(row=0, column=0, sticky="nsew")

        if keep_url:
            self.url_entry.insert(0, keep_url)
        self.show_screen("input")

    def show_screen(self, name: str):
        (self.input_screen if name == "input" else self.result_screen).tkraise()

    def on_theme_change(self, name: str):
        if self.busy or name == self.theme_name:
            return
        # Rebuild after the dropdown has finished closing
        self.after(20, lambda: self._apply_theme(name))

    def _apply_theme(self, name: str):
        keep = self.url_entry.get()
        self.theme_name = name
        self.c = THEMES[name]
        save_theme_name(name)
        self._build_ui(keep_url=keep)

    # ---- screen 1: input --------------------------------------------------

    def _build_input_screen(self, parent):
        c = self.c
        screen = ctk.CTkFrame(parent, fg_color=c["bg"])

        # theme picker (top-right)
        picker = ctk.CTkFrame(screen, fg_color="transparent")
        picker.place(relx=1.0, x=-24, y=20, anchor="ne")
        ctk.CTkLabel(picker, text="Theme:", font=ctk.CTkFont(size=13),
                     text_color=c["muted"]).pack(side="left", padx=(0, 8))
        self.theme_menu = ctk.CTkOptionMenu(
            picker, values=list(THEMES), width=170, height=32, corner_radius=10,
            variable=ctk.StringVar(value=self.theme_name), command=self.on_theme_change,
            fg_color=c["card"], text_color=c["text"], button_color=c["soft"],
            button_hover_color=c["border"], dropdown_fg_color=c["card"],
            dropdown_text_color=c["text"], dropdown_hover_color=c["soft"])
        self.theme_menu.pack(side="left", padx=(8, 0))

        center = ctk.CTkFrame(screen, fg_color="transparent")
        center.place(relx=0.5, rely=0.46, anchor="center")

        ctk.CTkLabel(center, text="Fact-check a tweet",
                     font=ctk.CTkFont(size=34, weight="bold"), text_color=c["text"]).pack(pady=(0, 25))

        row = ctk.CTkFrame(center, fg_color="transparent")
        row.pack()

        self.url_entry = ctk.CTkEntry(
            row, width=480, height=50, corner_radius=14, border_width=1,
            border_color=c["border"], fg_color=c["card"], text_color=c["text"],
            placeholder_text_color=c["muted"],
            placeholder_text="Paste a tweet URL",
            font=ctk.CTkFont(size=15))
        self.url_entry.pack(side="left", padx=(0, 10))
        self.url_entry.bind("<Return>", lambda _e: self.start_check())

        self.check_btn = ctk.CTkButton(
            row, text="Check", width=110, height=50, corner_radius=14,
            fg_color=c["accent"], hover_color=c["accent_hover"], text_color=c["accent_text"],
            font=ctk.CTkFont(size=15, weight="bold"), command=self.start_check)
        self.check_btn.pack(side="left")

        self.status_label = ctk.CTkLabel(center, text="", font=ctk.CTkFont(size=14),
                                         text_color=c["muted"], wraplength=560)
        self.status_label.pack(pady=(18, 0))

        self.progress = ctk.CTkProgressBar(center, width=300, height=6, mode="indeterminate",
                                           progress_color=c["accent"], fg_color=c["border"])

        ctk.CTkLabel(screen, text="Results are AI-generated and can be wrong. Always check the original sources.",
                     font=ctk.CTkFont(size=12), text_color=c["muted"]
                     ).place(relx=0.5, rely=0.96, anchor="center")
        return screen

    # ---- screen 2: result -------------------------------------------------

    def _build_result_screen(self, parent):
        c = self.c
        screen = ctk.CTkFrame(parent, fg_color=c["bg"])

        top = ctk.CTkFrame(screen, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(18, 0))
        ctk.CTkButton(top, text="←  Check another tweet", width=180, height=36, corner_radius=10,
                      fg_color="transparent", hover_color=c["soft"], text_color=c["text"],
                      font=ctk.CTkFont(size=14), anchor="w",
                      command=self.back_to_input).pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(screen, fg_color="transparent",
                                             scrollbar_button_color=c["scroll"],
                                             scrollbar_button_hover_color=c["scroll_hover"])
        self.scroll.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        return screen

    def show_result(self, author: str, tweet: str, result: dict):
        c = self.c
        if self.result_body is not None:
            self.result_body.destroy()
        body = ctk.CTkFrame(self.scroll, fg_color="transparent")
        body.pack(pady=(4, 20))
        # invisible spacer that fixes the column width
        ctk.CTkFrame(body, width=CONTENT_WIDTH, height=1, fg_color="transparent").pack()
        self.result_body = body

        self._tweet_card(body, author, tweet)
        self._verdict_card(body, result)
        self._method_section(body, result.get("method", ""))

        ctk.CTkLabel(self, text="Results are AI-generated and can be wrong. Always check the original sources.",
                     font=ctk.CTkFont(size=12), text_color=c["muted"], wraplength=WRAP,
                     justify="center").place(relx=0.5, rely=0.98, anchor="s")
        self.show_screen("result")

    def _tweet_card(self, parent, author, tweet):
        c = self.c
        card = ctk.CTkFrame(parent, fg_color=c["card"], corner_radius=16, border_width=1,
                            border_color=c["border"])
        card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(card, text="Tweet checked", font=ctk.CTkFont(size=12), text_color=c["muted"]
                     ).pack(anchor="w", padx=22, pady=(16, 0))
        ctk.CTkLabel(card, text=author or "@unknown", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=c["text"]).pack(anchor="w", padx=22, pady=(2, 0))
        ctk.CTkLabel(card, text=tweet, font=ctk.CTkFont(size=15), text_color=c["text"],
                     wraplength=WRAP, justify="left").pack(anchor="w", padx=22, pady=(6, 18))

    def _verdict_card(self, parent, result):
        v = VERDICTS.get(result.get("verdict"), VERDICTS["unverifiable"])
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0))))

        card = ctk.CTkFrame(parent, fg_color=v["bg"], corner_radius=16)
        card.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(card, text=f"{v['icon']}  {v['label']}", text_color=v["color"],
                     font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", padx=22, pady=(18, 2))

        # verdict-card text uses fixed neutral colours so it is readable in every theme
        ctk.CTkLabel(card, text=f"Confidence {int(confidence * 100)}%", text_color="#475467",
                     font=ctk.CTkFont(size=13)).pack(anchor="w", padx=22)
        bar = ctk.CTkProgressBar(card, height=8, corner_radius=4,
                                 progress_color=v["color"], fg_color="#FFFFFF")
        bar.set(confidence)
        bar.pack(fill="x", padx=22, pady=(6, 14))

        ctk.CTkLabel(card, text="Claim checked", text_color="#475467",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=22)
        ctk.CTkLabel(card, text=result.get("claim", ""), text_color="#101828", wraplength=WRAP,
                     justify="left", font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(anchor="w", padx=22, pady=(2, 10))
        ctk.CTkLabel(card, text=result.get("summary", ""), text_color="#101828", wraplength=WRAP,
                     justify="left", font=ctk.CTkFont(size=15)).pack(anchor="w", padx=22, pady=(0, 18))

    def _method_section(self, parent, method):
        if not method:
            return
        c = self.c
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x")
        detail = ctk.CTkLabel(wrapper, text=method, text_color=c["muted"], wraplength=WRAP,
                              justify="left", font=ctk.CTkFont(size=14))
        state = {"open": False}

        def toggle():
            if state["open"]:
                detail.pack_forget()
                btn.configure(text="▸  How we checked this")
            else:
                detail.pack(anchor="w", padx=12, pady=(0, 6))
                btn.configure(text="▾  How we checked this")
            state["open"] = not state["open"]

        btn = ctk.CTkButton(wrapper, text="▸  How we checked this", width=200, height=32,
                            fg_color="transparent", hover_color=c["soft"], text_color=c["text"],
                            anchor="w", font=ctk.CTkFont(size=14), command=toggle)
        btn.pack(anchor="w")

    # ---- actions ----------------------------------------------------------

    def back_to_input(self):
        self.url_entry.delete(0, "end")
        self.status_label.configure(text="", text_color=self.c["muted"])
        self.show_screen("input")
        self.url_entry.focus()

    def start_check(self):
        if self.busy:
            return
        url = self.url_entry.get().strip()
        if not url:
            self._set_error("Paste a tweet link first.")
            return
        if not is_tweet_url(url):
            self._set_error("That doesn't look like a tweet link. It should look like "
                            "https://x.com/username/status/123…")
            return

        self.busy = True
        self.check_btn.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.theme_menu.configure(state="disabled")
        self.status_label.configure(text="Checking… this can take a few seconds",
                                    text_color=self.c["muted"])
        self.progress.pack(pady=(14, 0))
        self.progress.start()

        # Run the (possibly slow) backend off the UI thread so the window stays responsive
        threading.Thread(target=self._work, args=(url,), daemon=True).start()
        self.after(100, self._poll)

    def _set_error(self, message):
        self.status_label.configure(text=message, text_color=ERROR)

    def _work(self, url):
        try:
            fetched = fetch_tweet(url)
            result = check_claim(fetched["text"])
            self.jobs.put(("ok", fetched.get("author", ""), fetched["text"], result))
        except Exception as exc:
            self.jobs.put(("error", str(exc) or "Something went wrong. Please try again."))

    def _poll(self):
        try:
            item = self.jobs.get_nowait()
        except queue.Empty:
            self.after(100, self._poll)
            return

        self.busy = False
        self.progress.stop()
        self.progress.pack_forget()
        self.check_btn.configure(state="normal")
        self.url_entry.configure(state="normal")
        self.theme_menu.configure(state="normal")

        if item[0] == "ok":
            _, author, tweet, result = item
            self.status_label.configure(text="")
            self.show_result(author, tweet, result)
        else:
            self._set_error(item[1])


def main():
    FactCheckApp().mainloop()


if __name__ == "__main__":
    main()
