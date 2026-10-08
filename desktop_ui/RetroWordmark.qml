// pipeRun derivative · dan-cun / github.com/dan-cun/lepao3 · LRL-1.0, noncommercial research.
import QtQuick

Canvas {
    id: brand
    objectName: "terminalWordmark"
    property bool animate: true
    property color ink: "#eeeeee"
    property color depthInk: "#888888"
    property color edgeInk: "#111111"
    property color shadowInk: "#666666"
    property real revealProgress: 1
    readonly property int pixelColumns: 41
    readonly property int pixelRows: 7
    opacity: revealProgress
    renderTarget: Canvas.Image; renderStrategy: Canvas.Immediate; antialiasing: false
    NumberAnimation { id: reveal; target: brand; property: "revealProgress"; from: 0; to: 1; duration: 240; easing.type: Easing.OutCubic }
    onAnimateChanged: if (!animate) { reveal.stop(); revealProgress = 1 }
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onInkChanged: requestPaint()
    onDepthInkChanged: requestPaint()
    onEdgeInkChanged: requestPaint()
    onShadowInkChanged: requestPaint()
    Component.onCompleted: { requestPaint(); if (animate && visible) reveal.start() }
    onPaint: {
        var c = getContext("2d"); c.reset(); c.clearRect(0, 0, width, height);
        if (width < 50 || height < 14) return;
        var glyphs = {
            P: ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
            I: ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
            E: ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
            R: ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
            U: ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
            N: ["10001", "11001", "11001", "10101", "10011", "10011", "10001"]
        }, bitmap = [];
        for (var r = 0; r < 7; ++r) bitmap.push("PIPERUN".split("").map(function(ch) { return glyphs[ch][r] }).join("0"));
        // Reserve the entire extrusion and its floor shadow inside the canvas.
        var depth = Math.max(8, Math.min(14, Math.floor(height * .12)));
        var ux = (width - depth - 8) / 41, uy = Math.min((height - depth - 16) / 7, ux * 1.3);
        var ox = 2, oy = Math.max(2, Math.floor((height - 7 * uy - depth - 12) / 2));
        function occupied(x, y) { return y >= 0 && y < 7 && x >= 0 && x < 41 && bitmap[y][x] === "1" }
        // A sparse grounded shadow, not another copy competing with the title.
        c.fillStyle = shadowInk;
        for (var groundRow = 0; groundRow < 3; ++groundRow) {
            c.globalAlpha = .38 - groundRow * .1;
            for (var groundCol = 0; groundCol < 41; ++groundCol) {
                var grounded = false;
                for (var sourceRow = 0; sourceRow < 7; ++sourceRow) grounded = grounded || occupied(groundCol, sourceRow);
                if (grounded && (groundCol + groundRow) % 2 === 0)
                    c.fillRect(Math.round(ox + groundCol * ux + depth), Math.round(oy + 7 * uy + depth + 2 + groundRow * 3), Math.max(2, Math.floor(ux * .65)), 2);
            }
        }
        c.globalAlpha = 1;
        for (var layer = 4; layer >= 0; --layer) {
            var sx = Math.round(depth * .65 * layer / 4), sy = Math.round(depth * layer / 4);
            c.fillStyle = layer === 0 ? ink : layer === 1 ? depthInk : shadowInk;
            for (r = 0; r < 7; ++r) for (var col = 0; col < 41; ++col) if (occupied(col, r)) {
                var x = Math.round(ox + col * ux), y = Math.round(oy + r * uy);
                c.fillRect(x + sx, y + sy, Math.round(ox + (col + 1) * ux) - x, Math.round(oy + (r + 1) * uy) - y);
            }
        }
        // Trace only the glyph perimeter, not a noisy grid between occupied cells.
        c.strokeStyle = edgeInk; c.lineWidth = 1; c.beginPath();
        for (r = 0; r < 7; ++r) for (col = 0; col < 41; ++col) if (occupied(col, r)) {
            var x0 = Math.round(ox + col * ux) + .5, x1 = Math.round(ox + (col + 1) * ux) - .5;
            var y0 = Math.round(oy + r * uy) + .5, y1 = Math.round(oy + (r + 1) * uy) - .5;
            if (!occupied(col, r - 1)) { c.moveTo(x0, y0); c.lineTo(x1, y0) }
            if (!occupied(col, r + 1)) { c.moveTo(x0, y1); c.lineTo(x1, y1) }
            if (!occupied(col - 1, r)) { c.moveTo(x0, y0); c.lineTo(x0, y1) }
            if (!occupied(col + 1, r)) { c.moveTo(x1, y0); c.lineTo(x1, y1) }
        }
        c.stroke();
    }
}
