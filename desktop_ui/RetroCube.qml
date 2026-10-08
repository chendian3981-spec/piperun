// pipeRun derivative · dan-cun / github.com/dan-cun/lepao3 · LRL-1.0, noncommercial research.
import QtQuick

Canvas {
    id: cube
    objectName: "terminalCube"
    property bool animate: true
    property bool paused: false
    property real phase: .64
    property real turnOffset: 0
    property real breathSeconds: 0
    property double lastTick: 0
    property real rowHeight: 22
    property color ink: "#eeeeee"
    property color rearInk: "#888888"
    property color baseInk: "#111111"
    readonly property int vertexCount: 8
    readonly property int edgeCount: 12
    readonly property int repaintInterval: 40
    readonly property int pixelSize: 4
    readonly property int coreBreathMs: 4800
    readonly property real corePulse: animate ? .5 - .5 * Math.cos(breathSeconds * Math.PI * 2 / 4.8) : .45
    readonly property string geometryMode: "complete-twelve-edge-pixel-wireframe"
    readonly property bool idleRunning: visible && animate && !paused
    renderTarget: Canvas.Image; renderStrategy: Canvas.Immediate; antialiasing: false
    function kick() {
        if (!idleRunning) return;
        turn.stop(); turn.from = turnOffset; turn.to = turnOffset + Math.PI / 2; turn.start();
    }
    NumberAnimation { id: turn; target: cube; property: "turnOffset"; duration: 700; easing.type: Easing.OutCubic }
    onPhaseChanged: requestPaint()
    onTurnOffsetChanged: requestPaint()
    onBreathSecondsChanged: requestPaint()
    onAnimateChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onInkChanged: requestPaint()
    onRearInkChanged: requestPaint()
    onBaseInkChanged: requestPaint()
    onIdleRunningChanged: { lastTick = 0; if (!idleRunning) turn.stop(); else requestPaint() }
    Component.onCompleted: requestPaint()
    Timer {
        interval: cube.repaintInterval; repeat: true; running: cube.idleRunning
        onTriggered: {
            var now = Date.now();
            if (cube.lastTick) {
                var delta = Math.max(0, Math.min(.08, (now - cube.lastTick) / 1000));
                cube.phase += delta * .48;
                cube.breathSeconds += delta;
            }
            cube.lastTick = now;
        }
    }
    onPaint: {
        var c = getContext("2d"); c.reset(); c.clearRect(0, 0, width, height);
        if (width < 24 || height < 24) return;
        var yaw = phase + turnOffset, pitch = .55 + Math.sin(yaw * .5) * .08, roll = .10;
        var cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch), cr = Math.cos(roll), sr = Math.sin(roll);
        function rotate(x, y, z) {
            var xx = x * cy + z * sy, zz = -x * sy + z * cy;
            var yy = y * cp - zz * sp; zz = y * sp + zz * cp;
            return [xx * cr - yy * sr, xx * sr + yy * cr, zz];
        }
        // A projected bounding sphere contains every orientation; leave 10px for caps/strokes.
        var distance = 5.5, bound = Math.sqrt(3) * distance / Math.sqrt(distance * distance - 3);
        var scale = Math.max(1, (Math.min(width, height) - 20) / (2 * bound)), points = [], edges = [];
        for (var i = 0; i < 8; ++i) {
            var v = rotate(i & 1 ? 1 : -1, i & 2 ? 1 : -1, i & 4 ? 1 : -1);
            var lens = distance / (distance - v[2]);
            points.push([width / 2 + v[0] * scale * lens, height / 2 - v[1] * scale * lens, v[2]]);
        }
        for (i = 0; i < 8; ++i) for (var bit = 1; bit <= 4; bit *= 2) {
            var j = i ^ bit; if (j < i) continue;
            var front = false;
            for (var axis = 1; axis <= 4; axis *= 2) if (axis !== bit) {
                var sign = i & axis ? 1 : -1;
                var n = rotate(axis === 1 ? sign : 0, axis === 2 ? sign : 0, axis === 4 ? sign : 0);
                if (n[2] * distance > 1) front = true;
            }
            edges.push({a: points[i], b: points[j], front: front, depth: (points[i][2] + points[j][2]) / 2});
        }
        edges.sort(function(a, b) { return a.front !== b.front ? (a.front ? 1 : -1) : a.depth - b.depth });
        var pixel = pixelSize, centerX = Math.round(width / (2 * pixel)) * pixel, centerY = Math.round(height / (2 * pixel)) * pixel;
        // Fixed-size stepped halo: stronger light without changing edge bounds or adding filters.
        c.fillStyle = ink;
        var radii = [28, 22, 16, 10, 6, 3], strengths = [.025 + .075 * corePulse, .04 + .12 * corePulse, .07 + .20 * corePulse, .12 + .30 * corePulse, .24 + .40 * corePulse, .60 + .35 * corePulse];
        for (i = 0; i < radii.length; ++i) {
            var radius = radii[i];
            c.globalAlpha = strengths[i];
            c.fillRect(centerX - radius, centerY - radius, radius * 2, radius * 2);
        }
        c.globalAlpha = 1;
        // Bresenham visits only cells on each edge; no loop over canvas pixels.
        function pixelEdge(a, b, dashed) {
            var x = Math.round(a[0] / pixel), y = Math.round(a[1] / pixel);
            var endX = Math.round(b[0] / pixel), endY = Math.round(b[1] / pixel);
            var dx = Math.abs(endX - x), dy = -Math.abs(endY - y);
            var sx = x < endX ? 1 : -1, sy = y < endY ? 1 : -1, error = dx + dy, count = 0;
            c.beginPath();
            while (true) {
                if (!dashed || count % 4 < 2) c.rect(x * pixel, y * pixel, pixel, pixel);
                if (x === endX && y === endY) break;
                var doubled = 2 * error;
                if (doubled >= dy) { error += dy; x += sx }
                if (doubled <= dx) { error += dx; y += sy }
                ++count;
            }
            c.fill();
        }
        for (i = 0; i < edges.length; ++i) {
            var e = edges[i]; c.fillStyle = e.front ? ink : rearInk;
            pixelEdge(e.a, e.b, !e.front);
        }
        for (i = 0; i < points.length; ++i) {
            c.fillStyle = points[i][2] > 0 ? ink : rearInk;
            c.fillRect(Math.round(points[i][0] / pixel) * pixel, Math.round(points[i][1] / pixel) * pixel, pixel, pixel);
        }
    }
}
