# Sourcing footage

## Search with yt-dlp

Flat search is the fastest way to survey a topic. It does **not** return upload dates:

```bash
yt-dlp "ytsearch15:<query>" --flat-playlist --no-warnings \
  --print "%(duration)s | %(title).60s | https://youtu.be/%(id)s"
```

To filter by recency you must fetch metadata per candidate — one network round trip each, so
shortlist first:

```bash
yt-dlp --skip-download --no-warnings \
  --print "%(upload_date)s|%(duration)s|%(width)sx%(height)s|%(title).50s" \
  "https://www.youtube.com/watch?v=<id>"
```

Check what resolutions actually exist before committing to a download:

```bash
yt-dlp -F "https://youtu.be/<id>"
```

Download the best available under a ceiling:

```bash
yt-dlp -f "bv*[height<=2160]+ba/b[height<=2160]/b" --merge-output-format mp4 \
  -o "%(id)s_%(title).50s.%(ext)s" "https://youtu.be/<id>"
```

### Behind a proxy

If a proxy is configured locally, every command needs it — `yt-dlp --proxy http://127.0.0.1:7897`.
Verify the exit region before trusting results; a search returning unrelated foreign content usually
means the proxy is off.

### Audio-only formats

`yt-dlp -F` lists them separately. Selecting `bv*+ba` picks both; for background plates you usually
want `-an` on the re-encode instead.

## Bilibili

`yt-dlp` handles both single videos and search, but the search endpoint rate-limits hard.

Direct download (needs the proxy if the CDN is region-restricted):

```bash
yt-dlp -f "bv*[height<=1080]+ba/b[height<=1080]/b" --merge-output-format mp4 \
  -o "%(title).60s.%(ext)s" "https://www.bilibili.com/video/BVxxxxxxxxxx"
```

Search API — returns `pubdate` directly, which YouTube search does not:

```
https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=<urlencoded>&page=1
```

Requirements and quirks:
- Fetch `https://www.bilibili.com/` first with a browser UA into a cookie jar, and send
  `Referer: https://www.bilibili.com/` on the API call. Without a session you get `code: -412`.
- Space requests **2-6 seconds** apart. Bulk querying triggers `HTTP 412 Precondition Failed`.
- `data.result[].pubdate` is a unix timestamp; `duration` is `"m:ss"` mixed-length, normalise it.
- `yt-dlp "bilisearch:"` also 412s frequently. The JSON API plus a cookie jar is more reliable.

## CCTV

Pages expose a `guid`; the player API resolves it to HLS:

```bash
# 1. pull the page and extract:  var guid = "<32 hex>"
# 2. query
curl "https://vdn.apps.cntv.cn/api/getHttpVideoInfo.do?pid=<guid>"
# → JSON with hls_url, video.totalLength, video.chapters[]
```

Then hand the HLS URL to ffmpeg:

```bash
ffmpeg -y -user_agent "Mozilla/5.0" -headers "Referer: https://tv.cctv.cn/" \
  -i "<hls_url>" -c copy -bsf:a aac_adtstoasc out.mp4
```

Constraints found in practice:
- `video.chapters[].url` is empty — no direct MP4 fallback.
- The public web player caps at **480x270** for many programmes regardless of `maxbr` or which CDN
  host you try. Verify the manifest's `RESOLUTION` before promising HD.
- Alternate `maxbr` values, `quality=1..4`, and other CDN hosts did not unlock higher bitrates.

## Hard blocks

- **`pexels.com`** returns 403 to non-browser clients; no page scraping.
- **WeChat articles (`mp.weixin.qq.com`)** return a ~17 KB shell with no `mpvideo` fields, under a
  normal UA, a `MicroMessenger` UA, and a cookie-session retry. Video cannot be extracted without a
  real client. Tell the user to save it in-app and hand over the file.
- Pages behind a DNS-poisoned host (resolving into `198.18.0.0/15`) need a proxy or VPN; check with
  `getent hosts <domain>` when a site times out that others do not.

## Verify before using

For every clip, extract a frame and look at it before it enters a deliverable. Confirm: no
burned-in text, no watermark, no people (if the brief says pure background), no scene change inside
the intended loop, and the correct resolution. Record source URL, author, license, resolution and
duration alongside the file — you will need them for an attribution slide.
