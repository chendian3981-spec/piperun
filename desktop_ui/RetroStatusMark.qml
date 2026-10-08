// pipeRun derivative · dan-cun / github.com/dan-cun/lepao3 · LRL-1.0, noncommercial research.
import QtQuick

Canvas {
    id: mark
    property string outcome: "success"
    property color ink: "#eeeeee"
    renderTarget: Canvas.Image; renderStrategy: Canvas.Immediate; antialiasing: false
    Accessible.name: outcome === "error" ? "操作失败" : "操作完成"
    onOutcomeChanged: requestPaint()
    onInkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    Component.onCompleted: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset(); c.clearRect(0, 0, width, height);
        var unit = Math.floor(Math.min(width, height) / 9);
        if (unit < 1) return;
        var bitmap = outcome === "error" ? [
            "110000011", "011000110", "001101100", "000111000", "000010000",
            "000111000", "001101100", "011000110", "110000011"
        ] : [
            "000000000", "000000011", "000000110", "000001100", "110011000",
            "011110000", "001100000", "000000000", "000000000"
        ];
        var ox = Math.floor((width - 9 * unit) / 2), oy = Math.floor((height - 9 * unit) / 2);
        c.fillStyle = ink;
        for (var row = 0; row < 9; ++row) for (var col = 0; col < 9; ++col)
            if (bitmap[row][col] === "1") c.fillRect(ox + col * unit, oy + row * unit, unit, unit);
    }
}
