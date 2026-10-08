// pipeRun derivative · dan-cun / github.com/dan-cun/lepao3 · LRL-1.0, noncommercial research.
import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
Button {
    id: control
    property bool primary: false
    property bool danger: false
    property bool animate: control.Window.window ? !!control.Window.window.motion : false
    property bool selected: false
    property bool navigationRow: false
    property bool consoleMode: false
    property real selectionWidth: width
    signal executeRequested()
    RetroPalette { id: fallbackColors }
    readonly property var uiColors: control.Window.window && control.Window.window.theme ? control.Window.window.theme : fallbackColors
    readonly property bool inverse: enabled && (selected || primary || (activeFocus && !navigationRow) || down)
    implicitHeight: 32; implicitWidth: Math.max(64, contentItem ? contentItem.implicitWidth + 20 : 64)
    padding: 2; font.family: control.Window.window ? control.Window.window.font.family : "Consolas"; focusPolicy: Qt.StrongFocus; hoverEnabled: true
    function keyboardActivate(event) {
        event.accepted = true;
        if (!enabled || event.isAutoRepeat) return;
        if (navigationRow) executeRequested(); else clicked();
    }
    Keys.onReturnPressed: function(event) { keyboardActivate(event) }
    Keys.onEnterPressed: function(event) { keyboardActivate(event) }
    background: Rectangle {
        width: control.selectionWidth
        color: control.inverse ? control.uiColors.selection : control.hovered && control.enabled ? control.uiColors.hover : "transparent"
        border.width: control.activeFocus && control.navigationRow && !control.selected ? 1 : 0
        border.color: control.uiColors.muted
        Behavior on color { ColorAnimation { duration: control.animate ? 130 : 0 } }
    }
    contentItem: Text {
        text: "[ " + control.text + " ]"; textFormat: Text.PlainText
        color: !control.enabled ? control.uiColors.disabled : control.inverse ? control.uiColors.accentText : control.uiColors.text
        font.family: control.font.family; font.pixelSize: 20
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; clip: true
        Behavior on color { ColorAnimation { duration: control.animate ? 130 : 0 } }
    }
}
