// pipeRun derivative · dan-cun / github.com/dan-cun/lepao3 · LRL-1.0, noncommercial research.
import QtQuick

Item {
    id: line
    required property var entry
    property var colors
    property string fontFamily: "Consolas"
    property int rowHeight: 28
    property int frame: 0
    property int typingSequence: -1
    property string typingText: ""
    readonly property string fullText: entry.fullText || ""
    readonly property string fullBody: entry.body || ""
    readonly property bool running: entry.outcome === "running"
    readonly property color messageColor: entry.outcome === "error" ? colors.error : colors.text
    readonly property real prefixWidth: Math.min(metrics.advanceWidth(entry.prefix || ""), width * .58)
    readonly property real markerWidth: Math.max(24, metrics.advanceWidth("M") * 2)
    readonly property real bodyLeft: prefixWidth + markerWidth
    readonly property real bodyWidth: Math.max(1, width - bodyLeft)
    readonly property string counterSuffix: running && entry.counters ? "  " + entry.counters : ""
    readonly property string completeBody: fullBody + counterSuffix + (running ? " ..." : "")
    signal selected()
    signal opened()
    height: Math.max(rowHeight, measure.implicitHeight) + 4
    Accessible.name: fullText
    FontMetrics { id: metrics; font.family: line.fontFamily; font.pixelSize: 20 }
    function escaped(value) { return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;") }
    Text {
        id: measure
        visible: false; x: line.bodyLeft; width: line.bodyWidth
        text: line.completeBody; textFormat: Text.PlainText; wrapMode: Text.Wrap
        font.family: line.fontFamily; font.pixelSize: 20
        lineHeightMode: Text.FixedHeight; lineHeight: line.rowHeight
    }
    Text {
        y: 2; width: line.prefixWidth; text: line.entry.prefix || ""
        color: line.colors.muted; elide: Text.ElideRight; textFormat: Text.PlainText
        font.family: line.fontFamily; font.pixelSize: 20
        lineHeightMode: Text.FixedHeight; lineHeight: line.rowHeight
    }
    Text {
        x: line.prefixWidth; y: 2; width: line.markerWidth
        visible: line.entry.outcome !== "success" && line.entry.outcome !== "error"
        text: line.running ? ["|", "/", "-", "\\"][line.frame % 4] : "·"
        color: line.colors.muted
        font.family: line.fontFamily; font.pixelSize: 20; textFormat: Text.PlainText
        lineHeightMode: Text.FixedHeight; lineHeight: line.rowHeight
    }
    RetroStatusMark {
        x: line.prefixWidth; y: 2; width: line.markerWidth - 4; height: line.rowHeight - 4
        visible: line.entry.outcome === "success" || line.entry.outcome === "error"
        outcome: line.entry.outcome
        ink: line.entry.outcome === "error" ? line.colors.error : line.colors.success
    }
    Text {
        x: line.bodyLeft; y: 2; width: line.bodyWidth
        text: {
            var body = line.entry.seq === line.typingSequence ? line.typingText : line.fullBody;
            var dots = [".  ", ".. ", "..."][Math.floor(line.frame / 4) % 3];
            return line.escaped(body) + (line.running ? '<font color="' + line.colors.muted + '">' + line.escaped(line.counterSuffix) + " " + dots + "</font>" : "");
        }
        textFormat: Text.StyledText; wrapMode: Text.Wrap; color: line.messageColor
        font.family: line.fontFamily; font.pixelSize: 20
        lineHeightMode: Text.FixedHeight; lineHeight: line.rowHeight
    }
    MouseArea { anchors.fill: parent; onClicked: line.selected(); onDoubleClicked: line.opened() }
}
