// pipeRun derivative · dan-cun / github.com/dan-cun/lepao3 · LRL-1.0, noncommercial research.
import QtQuick

Item {
    id: stars
    objectName: "terminalStars"
    property real seconds: 0
    property bool animate: true
    property color ink: "#eeeeee"
    clip: true
    // Stable coordinates: ten quiet anchors and six individually phased glints.
    readonly property var points: [
        [.03,.68,0,.34,0], [.12,.24,0,.45,0], [.22,.80,0,.28,0],
        [.31,.42,0,.40,0], [.40,.13,0,.28,0], [.49,.74,0,.38,0],
        [.58,.35,0,.30,0], [.69,.86,0,.36,0], [.83,.20,0,.32,0], [.96,.66,0,.42,0],
        [.18,.46,1,4.8,.2], [.37,.76,1,6.2,1.3], [.54,.18,1,5.6,2.1],
        [.72,.47,1,7.0,.7], [.89,.74,1,5.2,3.1], [.06,.18,1,6.6,2.6]
    ]
    Repeater {
        model: stars.points
        Item {
            required property var modelData
            readonly property bool glint: !!modelData[2]
            readonly property real pulse: stars.animate && glint ? Math.pow(.5 + .5 * Math.sin((stars.seconds + modelData[4]) * Math.PI * 2 / modelData[3]), 2) : .55
            width: glint ? 14 : 2; height: width
            x: Math.round(modelData[0] * (stars.width - width))
            y: Math.round(modelData[1] * (stars.height - height))
            opacity: glint ? .20 + .72 * pulse : modelData[3]
            Rectangle { anchors.centerIn: parent; width: 2; height: 2; color: stars.ink }
            Rectangle { visible: parent.glint; anchors.centerIn: parent; width: 2; height: 10; color: stars.ink; opacity: .68 }
            Rectangle { visible: parent.glint; anchors.centerIn: parent; width: 10; height: 2; color: stars.ink; opacity: .68 }
            Rectangle { visible: parent.glint; x: 6; y: 0; width: 2; height: 2; color: stars.ink; opacity: parent.pulse * .45 }
            Rectangle { visible: parent.glint; x: 6; y: 12; width: 2; height: 2; color: stars.ink; opacity: parent.pulse * .45 }
            Rectangle { visible: parent.glint; x: 0; y: 6; width: 2; height: 2; color: stars.ink; opacity: parent.pulse * .45 }
            Rectangle { visible: parent.glint; x: 12; y: 6; width: 2; height: 2; color: stars.ink; opacity: parent.pulse * .45 }
        }
    }
}
