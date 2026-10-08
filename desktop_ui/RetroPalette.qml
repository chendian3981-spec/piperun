// pipeRun derivative · dan-cun / github.com/dan-cun/lepao3 · LRL-1.0, noncommercial research.
import QtQuick
QtObject {
    property bool semanticColors: true
    readonly property color base: "#111111"
    readonly property color surface: "#111111"
    readonly property color overlay: "#202020"
    readonly property color line: "#777777"
    readonly property color text: "#eeeeee"
    readonly property color muted: "#aaaaaa"
    readonly property color incomplete: "#888888"
    readonly property color success: semanticColors ? "#86c99b" : "#eeeeee"
    readonly property color disabled: "#777777"
    readonly property color accent: "#eeeeee"
    readonly property color accentText: "#111111"
    readonly property color selection: "#eeeeee"
    readonly property color warning: semanticColors ? "#dcc28d" : "#eeeeee"
    readonly property color error: semanticColors ? "#ee8b88" : "#ffffff"
    readonly property color hover: "#333333"
    readonly property color scrim: "#b0000000"
}
