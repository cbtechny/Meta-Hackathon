"""Build the recording kit and a silent picture edit from the actual capture."""
from pathlib import Path
import json
import os
import re
import subprocess
import textwrap
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/counterpilot-reel'
SCENES = json.loads((SOURCE / 'scenes.json').read_text(encoding='utf-8'))
OUT.mkdir(parents=True, exist_ok=True)
WORK = OUT / '.work'
WORK.mkdir(exist_ok=True)
FFMPEG = os.environ.get('COUNTERPILOT_FFMPEG', str(ROOT / 'artifacts/reel-tools/browser-cache/ffmpeg-1011/ffmpeg-win64.exe'))


def timestamp(seconds, ass=False):
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h}:{m:02}:{s:02}.{ms // 10:02}' if ass else f'{h:02}:{m:02}:{s:02},{ms:03}'


def run(args, log):
    result = subprocess.run([FFMPEG, '-hide_banner', '-y', *args], cwd=OUT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (WORK / log).write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'Encoder failed; see {WORK / log}: {result.stderr[-1200:]}')
    return result.stderr


def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf', size)


def centered(draw, text, y, size, fill, bold=False):
    face = font(size, bold)
    for index, line in enumerate(text.splitlines()):
        draw.text((540, y + index * (size + 18)), line, font=face, fill=fill, anchor='mt')


def text_assets():
    narration = '\n\n'.join(f'{i + 1}. {s["title"].upper()}\n\n{s["narration"]}' for i, s in enumerate(SCENES))
    words = sum(len(s['narration'].split()) for s in SCENES)
    (OUT / 'VOICEOVER.txt').write_text(narration + '\n', encoding='utf-8')
    guide = ['# CounterPilot: The Hackathon Story', '',
             '**Target:** 3:45, 1080 × 1920, your voice over real screen recordings.', '',
             f'**Script:** {words} words. Aim for a relaxed read; the time marks are editing targets, not exact speech measurements.', '',
             'Record one narration section per take, leaving two seconds of quiet before and after each. Keep a steady microphone distance. Record a second take of any sentence you stumble over; there is no need to restart the whole script.', '',
             '## Script and screen sequence', '']
    for scene in SCENES:
        guide.extend([f'### {scene["start"] // 60}:{scene["start"] % 60:02}–{scene["end"] // 60}:{scene["end"] % 60:02} — {scene["title"]}', '', '**Say:**', '',
                      '\n\n'.join('> ' + paragraph for paragraph in scene['narration'].split('\n\n')), '',
                      '**Record:** ' + scene['record'], '', '**On-screen text:** ' + scene['overlay'], ''])
    guide.extend(['## Recording and edit checklist', '',
                  '- Start with a fresh chat and empty demo Garage. Use an isolated browser session to preserve existing bookmarks.',
                  '- Record the browser vertically, with the app text large enough to read. Keep demo labels visible.',
                  '- Capture the full conversation and close-ups of the checklist, three cards, evidence and Garage.',
                  '- Cut loading pauses while keeping the actual responses and action order. Do not replace responses with mockups.',
                  '- Fit the picture edit to your recorded narration. Replace provisional subtitle timings with timings from your actual voice.',
                  '- Use captions throughout. Keep them away from part numbers, questions and demo disclosures. Use the clean picture file if you want to position captions yourself.',
                  '- Music is optional; keep it low enough that every spoken word stays clear.',
                  '- Preview once with sound and once on a phone before uploading. This kit contains no recorded voice or music.', '',
                  '## Event fact check', '',
                  'Checked November 3, 2026 against [Meta’s official event page](https://dev.meta.ai/events/global-hackathon): official title, worldwide virtual format, ten-day build period, $1,000,000 total prize pool and Build for Your World theme. The prize amount is the entire event pool. No winner, finalist, endorsement or deadline claim is made.', '',
                  '## App claim boundary', '',
                  'The footage demonstrates the current local prototype with fictional catalog records and simulated fitment. AI interprets the request; deterministic catalog code supplies records. It does not establish purchasing, installation, availability, real-photo accuracy or measured customer time savings.', ''])
    (OUT / 'SCRIPT_AND_RECORDING_GUIDE.md').write_text('\n'.join(guide), encoding='utf-8')
    (OUT / 'FACEBOOK_CAPTION.txt').write_text("I'm building CounterPilot for the Meta Global AI Developer Hackathon: a parts-finder prototype that keeps multi-part requests organized, asks about missing details, and saves displayed results to Garage.\n\nThis walkthrough uses demonstration records with simulated fitment.\n\nIf you've worked a parts counter—or struggled to explain what your car needs—what should it handle next?\n\n#CounterPilot #MetaHackathon #BuildInPublic #Automotive\n", encoding='utf-8')
    captions = []
    for scene in SCENES:
        groups, current = [], ''
        for word in scene['narration'].split():
            if current and len(current) + len(word) + 1 > 69:
                groups.append(current)
                current = ''
            current += (' ' if current else '') + word
        if current:
            groups.append(current)
        total = sum(len(group.split()) for group in groups)
        cursor = scene['start'] + .3
        available = scene['end'] - scene['start'] - .6
        for group in groups:
            duration = available * len(group.split()) / total
            captions.append((cursor, cursor + duration - .08, '\n'.join(textwrap.wrap(group, width=38))))
            cursor += duration
    srt = '\n\n'.join(f'{i + 1}\n{timestamp(start)} --> {timestamp(end)}\n{text}' for i, (start, end, text) in enumerate(captions)) + '\n'
    (OUT / 'CAPTIONS_DRAFT.srt').write_text(srt, encoding='utf-8')
    header = '[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Segoe UI,42,&H00FFFFFF,&H00FFFFFF,&H00102E25,&H00102E25,0,0,0,0,100,100,0,0,3,6,0,2,70,70,24,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    events = []
    for start, end, text in captions:
        safe = text.replace('{', '').replace('}', '').replace('\n', r'\N')
        events.append(f'Dialogue: 0,{timestamp(start, True)},{timestamp(end, True)},Default,,0,0,0,,{safe}')
    (OUT / 'CAPTIONS_DRAFT.ass').write_text(header + '\n'.join(events) + '\n', encoding='utf-8')
    (OUT / 'scene-plan.json').write_text(json.dumps(SCENES, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    end = Image.new('RGB', (1080, 1920), '#f6f9f3')
    draw = ImageDraw.Draw(end)
    centered(draw, 'CounterPilot', 610, 102, '#173e32', True)
    centered(draw, 'What should it\nhandle next?', 820, 72, '#173e32', True)
    centered(draw, 'A hackathon prototype', 1160, 38, '#52634d')
    centered(draw, 'Demonstration catalog • Simulated fitment', 1230, 30, '#52634d')
    end.save(OUT / 'END_CARD.png')
    overlay = Image.new('RGBA', (1080, 1920))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((65, 1280, 1015, 1510), radius=28, fill='#173e32')
    centered(draw, 'One request.\nThree different parts.', 1320, 54, 'white', True)
    overlay.save(OUT / 'PROBLEM_OVERLAY.png')
    return words, len(captions)


def render():
    capture = json.loads((OUT / 'capture.json').read_text(encoding='utf-8'))
    assert len(capture['markers']) == 8 and len(capture['turns']) == 5
    assert all(turn['status'] == 200 for turn in capture['turns']) and not capture['errors']
    raw = OUT / 'raw/counterpilot-live-walkthrough.webm'
    clips = []
    encode = ['-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p', '-threads', '2', '-movflags', '+faststart']
    for index, marker in enumerate(capture['markers']):
        duration = marker['target_duration'] - (6 if index == 7 else 0)
        target = WORK / f'{index + 1:02}.mp4'
        # Playwright pads the 432x768 viewport into the larger video canvas;
        # remove that padding before scaling the genuine screen content.
        vf = f'crop=432:768:0:0,scale=1080:1920,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},setpts=PTS-STARTPTS'
        args = ['-ss', str(marker['start']), '-i', str(raw)]
        if index == 1:
            args += ['-i', 'PROBLEM_OVERLAY.png', '-filter_complex', f'[0:v]{vf}[base];[base][1:v]overlay=0:0:format=auto[out]', '-map', '[out]']
        else:
            args += ['-vf', vf]
        run([*args, *encode, str(target)], f'encode-{index + 1:02}.log')
        clips.append(target)
        print('Encoded ' + marker['id'], flush=True)
    ending = WORK / '09-end.mp4'
    run(['-loop', '1', '-i', 'END_CARD.png', '-t', '6', '-vf', 'fps=30,setsar=1', *encode, str(ending)], 'encode-end.log')
    clips.append(ending)
    playlist = WORK / 'concat.txt'
    playlist.write_text('\n'.join("file '" + str(clip).replace('\\', '/') + "'" for clip in clips), encoding='utf-8')
    run(['-f', 'concat', '-safe', '0', '-i', str(playlist), '-c', 'copy', '-map_metadata', '-1', '-movflags', '+faststart', 'CounterPilot_Reel_PICTURE_ONLY.mp4'], 'concat.log')
    # Leave a reserved caption band so no UI labels or part numbers are covered.
    run(['-i', 'CounterPilot_Reel_PICTURE_ONLY.mp4', '-vf', 'scale=972:1728,pad=1080:1920:54:0:color=0xf6f9f3,ass=CAPTIONS_DRAFT.ass', *encode, 'CounterPilot_Reel_CAPTION_TIMING_PREVIEW.mp4'], 'caption-preview.log')
    verification = {}
    for filename in ['CounterPilot_Reel_PICTURE_ONLY.mp4', 'CounterPilot_Reel_CAPTION_TIMING_PREVIEW.mp4']:
        log = run(['-i', filename, '-f', 'null', '-'], 'decode-' + filename + '.log')
        duration = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', log)
        assert duration and '1080x1920' in log and '30 fps' in log and 'Audio:' not in log
        seconds = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3])
        assert abs(seconds - 225) < .2, seconds
        verification[filename] = {'duration_seconds': seconds, 'width': 1080, 'height': 1920, 'fps': 30, 'audio': 'none; creator narration required', 'full_decode': 'passed'}
    sheet = Image.new('RGB', (1080, 1080), 'white')
    for index, second in enumerate([12, 46, 78, 110, 136, 163, 188, 222]):
        target = WORK / f'review-{index}.png'
        run(['-ss', str(second), '-i', 'CounterPilot_Reel_CAPTION_TIMING_PREVIEW.mp4', '-frames:v', '1', '-update', '1', str(target)], f'frame-{index}.log')
        picture = Image.open(target).convert('RGB').resize((270, 480))
        x, y = (index % 4) * 270, (index // 4) * 540
        sheet.paste(picture, (x, y))
        ImageDraw.Draw(sheet).text((x + 8, y + 490), f'{second // 60}:{second % 60:02} • Scene {index + 1}', font=font(18), fill='black')
    sheet.save(OUT / 'REVIEW_CONTACT_SHEET.jpg', quality=93)
    return verification


def finalize(words, caption_count, verification, visual_review=None):
    start = '''# Your CounterPilot Reel kit

1. Read `VOICEOVER.txt` and record your voice in eight short takes. Read only the paragraphs; headings label the takes. Leave two seconds of quiet around each take.
2. Use `CounterPilot_Reel_PICTURE_ONLY.mp4` as the clean, silent 3:45 picture edit. The screen actions are already recorded.
3. Put your narration over the picture edit, then adjust cuts and caption timings to match your delivery.
4. `CounterPilot_Reel_CAPTION_TIMING_PREVIEW.mp4` shows the proposed captions in a reserved lower band. Its timing is estimated from the script, not aligned to recorded speech.
5. Use `CAPTIONS_DRAFT.srt` for editable captions; re-time them after recording your voice. Do not treat these as finished speech-aligned captions.
6. Read `SCRIPT_AND_RECORDING_GUIDE.md` for the timed script, exact app inputs, shot directions and recording checklist.

The eight scenes follow the approved plan. The footage uses the actual app and five successful live Meta chat turns in an isolated browser with fictional vehicle details. There are no mocked UI responses. Garage saving is real within that isolated recording context. The official event page is shown in the opening. Waiting is trimmed at the beginning of the capture; the picture edit may be adjusted further to fit your read.

This is a silent first cut, not a finished narrated Reel. No generated voice, music or final audio has been added. Listen to your assembled narration and check phone readability before publishing. Publishing is not part of this package.

`raw/` retains the original WebM. `stills/` contains actual capture frames. `capture.json` records source timings and sanitized successful-turn summaries. `END_CARD.png` and `PROBLEM_OVERLAY.png` are editable-use graphics made from text, not invented logos. `FACEBOOK_CAPTION.txt` supplies suggested post copy. `VERIFICATION.json` records export checks.

Source: https://dev.meta.ai/events/global-hackathon (checked November 3, 2026). The $1,000,000 refers to the whole event prize pool. Prototype records have simulated fitment; no purchasing or installation claim is made.
'''
    (OUT / 'START_HERE.md').write_text(start, encoding='utf-8')
    (OUT / 'VERIFICATION.json').write_text(json.dumps({'script_words': words, 'planned_duration_seconds': 225, 'draft_caption_cues': caption_count,
        'subtitle_timing': 'proportional script estimates; requires creator voice recording and retiming', 'exports': verification,
        'sampled_frame_review': visual_review or 'pending manual review',
        'audio_review': 'not applicable yet; no audio supplied', 'phone_playback_review': 'pending creator review'}, indent=2) + '\n', encoding='utf-8')
    archive = OUT.parent / 'CounterPilot_Reel_Recording_Kit.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for item in OUT.rglob('*'):
            if item.is_file() and '.work' not in item.parts and ('raw' not in item.parts or item.name == 'counterpilot-live-walkthrough.webm'):
                bundle.write(item, Path('CounterPilot_Reel') / item.relative_to(OUT))
    print(f'Packaged {words} narration words and {caption_count} provisional caption cues. Archive: {archive}', flush=True)


if __name__ == '__main__':
    words, caption_count = text_assets()
    verification = render() if (OUT / 'raw/counterpilot-live-walkthrough.webm').exists() else {}
    finalize(words, caption_count, verification)
