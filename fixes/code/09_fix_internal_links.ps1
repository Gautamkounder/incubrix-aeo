# Run in the website source folder. Rewrites internal links from /page.html to the canonical /page (and /index.html to /).
Get-ChildItem -Recurse -Include *.html | ForEach-Object {
  $t = Get-Content $_.FullName -Raw
  $t = $t -replace 'href="https://incubrix\.com/index\.html"', 'href="https://incubrix.com/"'
  $t = $t -replace 'href="(https://incubrix\.com)?/index\.html"', 'href="/"'
  $t = $t -replace 'href="(https://incubrix\.com)?/([a-z0-9-]+)\.html"', 'href="$1/$2"'
  Set-Content $_.FullName $t -NoNewline -Encoding utf8
}
