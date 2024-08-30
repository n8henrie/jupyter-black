# Developer notes

## Testing

To see the websocket events in Firefox:

1. open inspector -> Network
2. set filter to `WS`
3. select a request (ones starting with `channels?` seem relevant)
4. go to the `Response` inspector
5. the data has up or down arrow to indicate sent / received

More info: <https://web.archive.org/web/20231127084426/https://firefox-source-docs.mozilla.org/devtools-user/network_monitor/inspecting_web_sockets/index.html>

Consider using `PWDEBUG=1` (or `make test-debug`) when debugging the playwright
test code.

MSPV:
    - 3.10
        - Replace `t.Union` with `|`
        - several places that match would work well
