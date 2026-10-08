// pipeRun derivative · dan-cun / github.com/dan-cun/lepao3 · LRL-1.0, noncommercial research.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQml.Models

ApplicationWindow {
    id: app
    objectName: "retroWorkbench"
    width: Math.ceil(80 * cellWidth + 24); height: 24 * cellHeight + 24
    minimumWidth: 420; minimumHeight: 320
    visible: true; color: theme.base
    font.family: backend.uiFont
    font.pixelSize: 20
    palette.window: theme.base
    palette.base: theme.base
    palette.text: theme.text
    palette.windowText: theme.text
    palette.button: theme.overlay
    palette.buttonText: theme.text
    palette.highlight: theme.selection
    palette.highlightedText: theme.accentText
    palette.accent: theme.accent
    FontMetrics { id: gridFont; font.family: app.font.family; font.pixelSize: 20 }
    readonly property real cellWidth: gridFont.advanceWidth("M")
    readonly property int cellHeight: Math.max(28, Math.ceil(gridFont.height) + 8)
    readonly property int gridColumns: Math.floor((width - 24) / cellWidth)
    readonly property int gridRows: Math.floor((height - 24) / cellHeight)
    property var s: backend.state
    readonly property var member: s.member || ({})
    property bool motion: true
    property bool stepSound: true
    property int focusStep: 0
    property int lastNextStep: -1
    property int pendingGuide: -1
    property bool stepFocusPending: false
    property int step: focusStep < 0 ? (s.nextStep || 0) : focusStep
    RetroPalette { id: colors; semanticColors: backend.semanticColors }
    property alias theme: colors
    readonly property color accent: theme.accent
    readonly property bool compact: gridColumns < 80 || gridRows < 24
    readonly property bool squeezed: gridRows < 24
    readonly property bool tiny: gridColumns < 80
    readonly property bool tooSmall: gridColumns < 60 || gridRows < 22
    property bool showGuide: false
    property bool followLogs: true
    property string currentRecord: ""
    property bool wasCapturing: false
    property real modeReveal: 1
    property real logActivity: 0
    readonly property bool decorationVisible: active && visible && !tooSmall && !settings.visible && !registration.visible && !resetDialog.visible && !detailPopup.visible && !recordPopup.visible && !introPopup.visible && !backend.confirmation.open && !accounts.popup.visible
    readonly property bool ambientRunning: motion && decorationVisible && !compact
    readonly property real ambientSeconds: terminalCube ? terminalCube.breathSeconds : 0
    property int logFrame: 0
    Timer {
        interval: 160; repeat: true
        running: app.motion && app.decorationVisible && !!app.s.blocked
        onTriggered: app.logFrame = (app.logFrame + 1) % 12
    }
    onDecorationVisibleChanged: if (!decorationVisible) { if (logCue) logCue.stop(); logActivity = 0; if (modeFade) modeFade.complete() }
    onMotionChanged: if (!motion) { if (logCue) logCue.stop(); logActivity = 0; if (modeFade) modeFade.complete() }
    NumberAnimation { id: modeFade; target: app; property: "modeReveal"; from: .6; to: 1; duration: 160; easing.type: Easing.OutCubic }
    SequentialAnimation {
        id: logCue
        NumberAnimation { target: app; property: "logActivity"; to: .65; duration: 240; easing.type: Easing.InOutSine }
        NumberAnimation { target: app; property: "logActivity"; to: 0; duration: 520; easing.type: Easing.OutSine }
    }
    RetroTypewriter {
        id: logTyper; objectName: "logTypewriter"
        animate: app.motion && app.decorationVisible && app.followLogs
    }
    readonly property string interfaceMode: "button-driven-terminal"
    readonly property var labels: ["添加账号", "获取账号", "检查账号", "确认提交", "查看结果"]
    readonly property var descriptions: ["称呼随你填，学号要和小程序里一致。", "先点获取，倒计时内登录一次小程序。", "只做检查，不上传，也不提交。", "先看清账号和说明，不确定就取消。", "结果不明先查，别重复提交。"]
    readonly property string captureHeading: !s.capturing ? "获取登录信息" : s.capturePhase === "waiting_login" ? "现在登录小程序" : s.capturePhase === "stabilizing" ? "找到账号了，稍等一下" : s.capturePhase === "finishing" ? "正在恢复正常网络" : "先完成电脑弹窗授权"
    readonly property string captureHint: !s.capturing ? descriptions[1] : s.capturePhase === "waiting_login" ? "请在倒计时内，在「数体智慧体育」小程序里登录本人账号。不是登录微信。" : s.capturePhase === "stabilizing" ? "账号对上了。停留在当前页面，等软件保存就好。" : s.capturePhase === "finishing" ? "等网络恢复好，再点检查账号。" : "先按电脑弹窗授权，等倒计时出现再登录小程序。"
    property string softNotice: ""
    function interactionFeedback() {
        if (!motion || !decorationVisible) return;
        if (terminalCube) terminalCube.kick();
        if (modeFade) modeFade.restart();
    }
    onStepChanged: interactionFeedback()
    function canStep(index) {
        if (s.blocked || s.recoveryPending || registration.visible || resetDialog.visible || settings.visible || detailPopup.visible || recordPopup.visible || introPopup.visible || backend.confirmation.open) return false;
        if (index === 0) return true;
        if (index === 1) return !!s.selected;
        if (index === 2) return !!member.ready;
        if (index === 3) return !!member.can_submit;
        return !!member.can_watch;
    }
    readonly property bool navigationAllowed: !s.blocked && !registration.visible && !resetDialog.visible && !settings.visible && !recordPopup.visible && !detailPopup.visible && !introPopup.visible && !backend.confirmation.open
    readonly property var titles: ["添加本人账号", "连接登录信息", "检查登录信息", "核对后再提交", "查看处理结果"]
    readonly property string guideTitle: s.recoveryPending ? "先恢复网络" : s.capturing ? captureHeading : s.running && s.jobKind === "submit" ? "正在提交，请勿强退" : titles[step]
    readonly property string guideHint: s.recoveryPending ? "先恢复网络；若仍失败，请导出诊断发回。" : s.capturing || step === 1 ? captureHint : descriptions[step]
    readonly property string actionText: s.capturing ? "正在获取" : s.running || s.busy ? "处理中" : labels[step]
    readonly property string stepReason: s.blocked ? "" : s.recoveryPending ? "请先恢复网络。" : step > 0 && !s.selected ? "请先添加本人账号。" : step === 2 && !member.ready ? "请先获取登录信息。" : step === 3 && member.attempted ? "今天已有提交尝试，请查看结果，别重复提交。" : step === 3 && !member.can_submit ? "请先通过只读检查。" : step === 4 && !member.can_watch ? "请先获取登录信息。" : ""
    function runStep(index) {
        if (!canStep(index)) return;
        focusStep = index;
        if (compact) showGuide = index === 1;
        if (index === 0) registration.open();
        else if (index === 1) backend.action("capture");
        else if (index === 2) backend.action("build");
        else if (index === 3) backend.prepare();
        else backend.action("watch");
    }
    Connections {
        target: backend
        function onLogsChanged() {
            logTyper.receive([backend.latestConsoleEntry], false);
            if (app.motion && app.decorationVisible && logCue) logCue.restart();
            if (app.followLogs) Qt.callLater(function() { terminalLog.followLatest() });
        }
        function onReopened() { app.softNotice = "软件已打开，请在这里继续。"; softNoticeTimer.restart() }
        function onEscapePressed() {
            if (backend.confirmation.open) backend.cancelConfirmation();
            else if (introPopup.visible) introPopup.close();
            else if (resetDialog.visible) resetDialog.close();
            else if (registration.visible) registration.close();
            else if (settings.visible) settings.close();
            else if (recordPopup.visible) recordPopup.close();
            else if (detailPopup.visible) detailPopup.close();
            else { app.showGuide = false; app.focusStep = -1 }
        }
        function onRegistered() { app.stepFocusPending = true; registration.close(); personName.clear(); student.clear() }
        function onAccountsReset() { resetDialog.close(); app.focusStep = 0; app.stepFocusPending = true }
        function onChanged() {
            var current = backend.state, previous = app.lastNextStep;
            if (current.capturing && !app.wasCapturing && app.compact) app.showGuide = true;
            app.wasCapturing = !!current.capturing;
            if (current.nextStep !== previous) {
                app.lastNextStep = current.nextStep;
                if (previous >= 0) { app.focusStep = current.nextStep; app.stepFocusPending = true }
                if (!current.capturing) app.showGuide = false;
                app.pendingGuide = previous >= 0 && current.nextStep > previous ? current.nextStep : -1;
            }
            if (app.pendingGuide >= 0 && !current.blocked) {
                if (!current.error && app.stepSound) backend.stepFeedback();
                app.pendingGuide = -1;
            }
            if (app.stepFocusPending && !current.blocked) Qt.callLater(function() { app.focusSelectedTask() });
        }
    }

    component Frame: Rectangle { color: app.theme.surface; border.color: app.theme.line; border.width: 1 }
    component LabelText: Text { color: app.theme.text; font.family: app.font.family; font.pixelSize: 20; textFormat: Text.PlainText }
    component SmallText: LabelText { color: app.theme.muted; font.pixelSize: 20 }
    component Cell: Text {
        color: app.theme.text; font.family: app.font.family; font.pixelSize: 20
        textFormat: Text.PlainText; renderType: Text.NativeRendering
        height: app.cellHeight; verticalAlignment: Text.AlignVCenter; clip: true
        elide: Text.ElideRight
    }
    component Rule: Cell {
        id: rule
        property int junction: -1
        property int pulseStart: -1
        property int pulseCells: 7
        property real pulsePeriod: 6.4
        property real pulseOffset: 0
        width: dashboard.width; color: app.theme.line
        text: {
            var line = "+" + "-".repeat(Math.max(0, app.gridColumns - 2)) + "+";
            return junction > 0 && junction < app.gridColumns - 1 ? line.slice(0, junction) + "+" + line.slice(junction + 1) : line;
        }
        Cell {
            visible: app.motion && !app.compact && rule.pulseStart > 0
            x: rule.pulseStart * dashboard.cw; width: rule.pulseCells * dashboard.cw
            text: "-".repeat(rule.pulseCells); color: app.theme.text
            opacity: .08 + .30 * (.5 - .5 * Math.cos(app.ambientSeconds * Math.PI * 2 / rule.pulsePeriod + rule.pulseOffset))
        }
    }
    component SlidePopup: Popup {
        id: sheet
        property var previousFocus: null
        property bool restoreTaskFocus: false
        onAboutToShow: previousFocus = app.activeFocusItem
        parent: Overlay.overlay
        x: (parent.width - width) / 2; y: (parent.height - height) / 2
        enter: Transition { NumberAnimation { id: revealSheet; property: "opacity"; from: 0; to: 1; duration: app.motion ? 160 : 0; easing.type: Easing.OutCubic } }
        exit: Transition { NumberAnimation { id: hideSheet; property: "opacity"; from: 1; to: 0; duration: app.motion ? 100 : 0; easing.type: Easing.InCubic } }
        Connections {
            target: app
            function onMotionChanged() {
                if (!app.motion) {
                    revealSheet.complete(); hideSheet.complete();
                    Qt.callLater(function() { if (sheet.visible) sheet.opacity = 1 });
                }
            }
        }
        Connections {
            target: sheet
            function onClosed() {
                var previous = sheet.previousFocus;
                Qt.callLater(function() {
                    if (sheet.restoreTaskFocus || (previous && String(previous.objectName).indexOf("terminalStep-") === 0)) app.focusSelectedTask();
                    else if (previous && previous.visible && previous.enabled) previous.forceActiveFocus(Qt.OtherFocusReason);
                });
            }
        }
    }
    component Check: CheckBox {
        id: check
        contentItem: LabelText { text: check.text; leftPadding: 32; wrapMode: Text.Wrap; verticalAlignment: Text.AlignVCenter }
        indicator: Text {
            text: check.checked ? "[x]" : "[ ]"; font.family: app.font.family; font.pixelSize: 20
            color: check.activeFocus ? app.theme.accentText : app.theme.text
            y: (check.height - height) / 2
            Rectangle { anchors.fill: parent; color: check.activeFocus ? app.theme.selection : "transparent"; z: -1 }
        }
    }
    component Field: TextField {
        color: app.theme.text; placeholderTextColor: app.theme.muted; font.family: app.font.family; font.pixelSize: 20
        implicitHeight: 44; leftPadding: 10; selectByMouse: true
        background: Rectangle { color: app.theme.surface; border.width: parent.activeFocus ? 2 : 1; border.color: parent.activeFocus ? app.theme.text : app.theme.line }
    }
    component Metric: ColumnLayout {
        Layout.minimumWidth: 85
        property string value: "0"
        property string caption: ""
        LabelText { text: parent.value; Layout.fillWidth: true; elide: Text.ElideRight; font.weight: Font.DemiBold }
        SmallText { text: parent.caption; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight }
    }
    readonly property var keymap: [
        {key: "1", label: "1-5 选择", step: 0}, {key: "2", label: "", step: 1},
        {key: "3", label: "", step: 2}, {key: "4", label: "", step: 3}, {key: "5", label: "", step: 4},
        {key: "Up", label: "Up/Down 移动", delta: -1}, {key: "Down", label: "", delta: 1}
    ]
    readonly property string keyHints: keymap.filter(function(k) { return !!k.label }).map(function(k) { return k.label }).join("  ") + "  Enter 执行" + (app.compact ? "" : "  Tab 焦点")
    function choose(index) {
        if (!navigationAllowed) return;
        focusStep = Math.max(0, Math.min(4, index));
        var item = taskRepeater.itemAt(focusStep);
        if (item) item.forceActiveFocus();
    }
    function focusSelectedTask() {
        if (!navigationAllowed || accounts.popup.visible || tooSmall) return;
        var item = taskRepeater.itemAt(step);
        if (item && item.enabled) { item.forceActiveFocus(Qt.OtherFocusReason); stepFocusPending = false }
    }
    Instantiator {
        model: app.keymap
        delegate: Shortcut {
            required property var modelData
            sequence: modelData.key
            enabled: app.navigationAllowed && !accounts.activeFocus && !accounts.popup.visible && !terminalLog.activeFocus && !app.tooSmall
            onActivated: app.choose(modelData.step !== undefined ? modelData.step : (app.step + modelData.delta + 5) % 5)
        }
    }
    Shortcut {
        sequence: "F1"
        enabled: !registration.visible && !resetDialog.visible && !backend.confirmation.open && !detailPopup.visible && !recordPopup.visible && !introPopup.visible
        onActivated: settings.open()
    }
    readonly property var taskCompleted: [!!s.selected, !!member.ready,
        !!member.checked, !!member.submitted, !!member.reviewed]
    readonly property var taskStates: taskCompleted.map(function(done) { return done ? "已完成" : "未完成" })
    readonly property var operationModes: ["LOCAL / 仅保存到本机", "CAPTURE / 临时网络连接", "READ ONLY / 不上传、不提交", "CONFIRM / 需本人确认", "READ ONLY / 只复核结果"]
    readonly property var system: backend.metrics
    function percent(value) { return value === null || value === undefined ? "--" : Math.round(value) + "%" }
    function clock(value) {
        if (value === undefined) return "--:--";
        return String(Math.floor(value / 60)).padStart(2, "0") + ":" + String(value % 60).padStart(2, "0");
    }
    onActiveChanged: backend.setMetricsEnabled(active && visible)
    onVisibleChanged: backend.setMetricsEnabled(active && visible)
    Component.onCompleted: {
        backend.setMetricsEnabled(active && visible);
        logTyper.receive([backend.latestConsoleEntry], true);
        Qt.callLater(function() { if (backend.firstLaunch) introPopup.open(); else app.focusSelectedTask() });
    }
    FocusScope {
        id: dashboard
        anchors.fill: parent; anchors.margins: 12; focus: true
        visible: !app.tooSmall
        readonly property real cw: app.cellWidth
        readonly property real rh: app.cellHeight
        readonly property int split: Math.floor(app.gridColumns * .47)
        readonly property int headerSplit: Math.floor(app.gridColumns * .56)
        readonly property int metricColumns: app.gridColumns - headerSplit - 23
        readonly property int tasksTop: app.compact ? 4 : 10
        readonly property int actionRow: app.compact ? 12 : 16
        readonly property int eventRow: app.compact ? 14 : 17
        readonly property real taskLeft: cw * (app.compact ? 2 : split + 2)
        readonly property real taskWidth: cw * (app.compact ? app.gridColumns - 4 : app.gridColumns - split - 4)
        readonly property real statusWidth: Math.ceil(gridFont.advanceWidth("未完成") + cw * 2)
        readonly property real statusLeft: taskWidth - statusWidth - cw
        Keys.onReturnPressed: function(event) { if (!accounts.activeFocus && !accounts.popup.visible) { app.runStep(app.step); event.accepted = true } }
        Keys.onEnterPressed: function(event) { if (!accounts.activeFocus && !accounts.popup.visible) { app.runStep(app.step); event.accepted = true } }
        Rule { y: 0 }
        RetroButton {
            id: settingsLink; objectName: "settingsButton"
            x: dashboard.cw * 2; y: 0
            width: gridFont.advanceWidth("[ F1 说明 / 设置 ]") + 24; implicitHeight: dashboard.rh
            text: "F1 说明 / 设置"; onClicked: settings.open()
            background: Rectangle { color: settingsLink.inverse ? app.theme.selection : settingsLink.hovered ? app.theme.hover : app.theme.base }
        }
        Cell {
            color: app.theme.line; text: new Array(Math.max(0, app.gridRows - 2)).fill("|").join("\n")
            y: dashboard.rh; height: dashboard.height - dashboard.rh * 2; width: dashboard.cw
            lineHeightMode: Text.FixedHeight; lineHeight: dashboard.rh
        }
        Cell {
            color: app.theme.line; text: new Array(Math.max(0, app.gridRows - 2)).fill("|").join("\n")
            x: (app.gridColumns - 1) * dashboard.cw; y: dashboard.rh; height: dashboard.height - dashboard.rh * 2; width: dashboard.cw
            lineHeightMode: Text.FixedHeight; lineHeight: dashboard.rh
        }
        Rule { y: (app.gridRows - 1) * dashboard.rh }
        RetroWordmark {
            id: wordmark
            visible: !app.compact; x: dashboard.cw * 2; y: dashboard.rh * 3.65
            width: (dashboard.headerSplit - 3) * dashboard.cw; height: 4.1 * dashboard.rh
            animate: app.motion; ink: app.theme.text; depthInk: app.theme.muted; edgeInk: app.theme.base
            Accessible.name: "PIPERUN"
        }
        RetroStars {
            visible: !app.compact
            x: wordmark.x; y: dashboard.rh * 1.1
            width: wordmark.width; height: dashboard.rh * 2.2
            seconds: app.ambientSeconds; animate: app.motion
            ink: app.theme.text
        }
        Cell { visible: app.compact; x: dashboard.cw * 2; y: dashboard.rh; text: "pipeRun"; color: app.theme.muted }
        Item {
            visible: !app.compact; x: dashboard.cw * (dashboard.headerSplit + 2); y: dashboard.rh
            width: dashboard.cw * dashboard.metricColumns; height: 7 * dashboard.rh
            Cell { text: "SYSTEM"; font.bold: true }
            Column {
                y: dashboard.rh; spacing: 0
                Repeater {
                    model: [
                        {name: "CPU", value: app.system.cpu},
                        {name: "RAM", value: app.system.ram},
                        {name: "DISK", value: app.system.disk}
                    ]
                    Item {
                        required property var modelData
                        width: dashboard.cw * dashboard.metricColumns; height: dashboard.rh * 2
                        Cell { text: modelData.name; color: app.theme.muted }
                        Cell { width: parent.width; horizontalAlignment: Text.AlignRight; text: app.percent(modelData.value) }
                        Cell {
                            y: dashboard.rh; width: parent.width; color: app.theme.muted
                            text: {
                                var size = Math.max(4, Math.min(24, dashboard.metricColumns - 2));
                                if (modelData.value === null || modelData.value === undefined) return "[  --  ]";
                                var used = Math.max(0, Math.min(size, Math.round(modelData.value * size / 100)));
                                return "[" + "#".repeat(used) + "-".repeat(size - used) + "]";
                            }
                        }
                    }
                }
            }
        }
        RetroCube {
            id: terminalCube
            visible: !app.compact && !app.tooSmall
            x: (app.gridColumns - 20) * dashboard.cw; y: dashboard.rh
            rowHeight: dashboard.rh; width: dashboard.cw * 18; height: dashboard.rh * 7
            animate: app.motion; ink: app.theme.text; rearInk: app.theme.muted; baseInk: app.theme.base
            paused: !app.ambientRunning
        }
        Rule { visible: !app.compact; y: dashboard.rh * 8; junction: dashboard.split; pulseStart: app.gridColumns - 14; pulseCells: 9; pulsePeriod: 6.4 }
        Cell {
            visible: !app.compact; x: dashboard.split * dashboard.cw; y: dashboard.rh * 9
            text: new Array(8).fill("|").join("\n"); width: dashboard.cw; height: dashboard.rh * 8
            lineHeightMode: Text.FixedHeight; lineHeight: dashboard.rh; color: app.theme.line
        }
        Cell { visible: !app.compact; x: dashboard.cw * 2; y: dashboard.rh * 9; text: "RUNTIME"; font.bold: true }
        Cell {
            x: dashboard.taskLeft + dashboard.cw; y: dashboard.rh * (app.compact ? 3 : 9)
            width: dashboard.statusLeft - dashboard.cw * 2; text: "TASKS"; font.bold: true
        }
        Cell {
            objectName: "taskStatusHeader"
            x: dashboard.taskLeft + dashboard.statusLeft; y: dashboard.rh * (app.compact ? 3 : 9)
            width: dashboard.statusWidth; horizontalAlignment: Text.AlignLeft; text: "状态"; color: app.theme.muted
        }
        Cell {
            x: dashboard.cw * 2; y: dashboard.rh * (app.compact ? 2 : 10)
            text: "ACCOUNT"; color: app.theme.muted
        }
        ComboBox {
            id: accounts; objectName: "accounts"
            x: dashboard.cw * 11; y: dashboard.rh * (app.compact ? 2 : 10)
            width: dashboard.cw * (app.compact ? app.gridColumns - 14 : dashboard.split - 13); height: dashboard.rh
            model: s.members || []; textRole: "label"; valueRole: "key"; enabled: !s.blocked; padding: 0
            font.family: app.font.family; font.pixelSize: 20
            currentIndex: { var a = s.members || []; for (var i = 0; i < a.length; i++) if (a[i].key === s.selected) return i; return -1 }
            onActivated: backend.selectMember(currentValue)
            background: Rectangle { color: accounts.activeFocus ? app.theme.hover : app.theme.base; border.color: app.theme.line; border.width: 1 }
            contentItem: LabelText {
                text: accounts.displayText || "未添加"; leftPadding: 6; rightPadding: 20; elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
            indicator: LabelText { text: "v"; x: accounts.width - 18; anchors.verticalCenter: parent.verticalCenter }
            delegate: ItemDelegate {
                required property var modelData
                required property int index
                width: accounts.width; text: modelData.label; highlighted: accounts.highlightedIndex === index
                contentItem: LabelText { text: parent.text; elide: Text.ElideRight; color: parent.highlighted ? app.theme.accentText : app.theme.text }
                background: Rectangle { color: parent.highlighted ? app.theme.selection : app.theme.surface }
            }
            popup: Popup {
                y: accounts.height; width: accounts.width; implicitHeight: Math.min(contentItem.implicitHeight + 2, dashboard.height / 2); padding: 1
                background: Frame {}
                contentItem: ListView { clip: true; implicitHeight: contentHeight; model: accounts.popup.visible ? accounts.delegateModel : null; currentIndex: accounts.highlightedIndex; ScrollBar.vertical: ScrollBar {} }
            }
        }
        Column {
            visible: !app.compact; x: dashboard.cw * 2; y: dashboard.rh * 11
            width: dashboard.cw * (dashboard.split - 4)
            Cell { width: parent.width; text: "登录信息  " + (member.consumed ? "已消耗" : member.ready ? "已获取" : "未获取") }
            Cell { width: parent.width; text: "当前阶段  " + (s.stage || "等待操作") }
            Cell { width: parent.width; text: "网络记录  " + (s.recoveryPending ? "需要恢复" : "无待恢复") }
        }
        Column {
            x: dashboard.taskLeft; y: dashboard.rh * dashboard.tasksTop
            width: dashboard.taskWidth
            Repeater {
                id: taskRepeater
                model: app.labels
                RetroButton {
                    id: task
                    required property int index
                    required property string modelData
                    objectName: "terminalStep-" + index
                    width: parent.width; implicitHeight: dashboard.rh; selected: app.step === index; navigationRow: true; padding: 0
                    enabled: app.navigationAllowed
                    selectionWidth: dashboard.statusLeft - dashboard.cw
                    onClicked: app.choose(index)
                    onExecuteRequested: app.runStep(app.step)
                    onActiveFocusChanged: if (activeFocus && app.navigationAllowed) app.focusStep = index
                    Accessible.name: "第" + (index + 1) + "步 " + modelData + "，点击选择，Enter执行"
                    contentItem: Item {
                        Cell {
                            width: dashboard.statusLeft - dashboard.cw; height: parent.height
                            leftPadding: dashboard.cw
                            text: "[" + (task.index + 1) + "] " + task.modelData
                            color: task.inverse ? app.theme.accentText : task.enabled ? app.theme.text : app.theme.disabled
                            Behavior on color { ColorAnimation { duration: task.animate ? 130 : 0 } }
                        }
                        Cell {
                            objectName: "taskStatus-" + task.index
                            x: dashboard.statusLeft
                            width: dashboard.statusWidth; height: parent.height; horizontalAlignment: Text.AlignLeft
                            text: app.taskStates[task.index]
                            color: app.taskCompleted[task.index] ? app.theme.text : app.theme.incomplete
                            Behavior on color { ColorAnimation { duration: task.animate ? 130 : 0 } }
                        }
                    }
                }
            }
        }
        Cell {
            x: dashboard.cw * 2; y: dashboard.rh * (app.compact ? 9 : 14)
            width: dashboard.cw * (app.compact ? app.gridColumns - 4 : dashboard.split - 4)
            height: dashboard.rh * (app.compact ? 3 : 2)
            text: app.stepReason || app.guideHint; wrapMode: Text.Wrap
            maximumLineCount: app.compact ? 3 : 2; color: app.theme.muted
        }
        Cell {
            visible: !app.compact; x: dashboard.cw * (dashboard.split + 2); y: dashboard.rh * 15
            width: dashboard.cw * (app.gridColumns - dashboard.split - 4); color: app.theme.muted
            text: s.capturing ? "CAPTURE / 正在获取" : app.operationModes[app.step]
            opacity: app.modeReveal
        }
        RetroButton {
            id: primaryAction; objectName: "primaryAction"
            x: dashboard.cw * (app.compact ? 2 : dashboard.split + 2); y: dashboard.rh * dashboard.actionRow
            width: dashboard.cw * (app.compact ? app.gridColumns - 4 : app.gridColumns - dashboard.split - 4)
            implicitHeight: dashboard.rh; text: app.actionText + " / Enter"; primary: true
            enabled: app.canStep(app.step); onClicked: app.runStep(app.step)
        }
        Row {
            x: dashboard.cw * 2; y: dashboard.rh * (app.compact ? 13 : 16); spacing: dashboard.cw
            RetroButton {
                objectName: "stopAction"; text: s.capturing ? "停止获取" : "停止检查"; implicitHeight: dashboard.rh
                visible: !!s.capturing || (!!s.running && s.jobKind !== "submit"); enabled: !s.busy
                onClicked: backend.action(s.capturing ? "desktop-recover" : "stop-job")
            }
            RetroButton {
                objectName: "recoveryAction"; text: s.error === "E_RECOVERY" ? "导出诊断" : "恢复网络"; implicitHeight: dashboard.rh
                visible: !!s.recoveryPending; enabled: !s.blocked
                onClicked: s.error === "E_RECOVERY" ? backend.exportDiagnostics() : backend.action("desktop-recover")
            }
            Cell { visible: !s.capturing && !s.running && !s.recoveryPending; text: "SESSION  " + app.clock(app.system.seconds); color: app.theme.muted }
        }
        Rule { y: dashboard.rh * dashboard.eventRow; junction: app.compact ? -1 : dashboard.split; pulseStart: app.gridColumns - 6; pulseCells: 4; pulsePeriod: 7.6; pulseOffset: 2.2 }
        Rectangle {
            objectName: "newLogCue"
            x: dashboard.cw * 2; y: dashboard.rh * (dashboard.eventRow + 1) - 2
            width: dashboard.cw * 9; height: 2; color: app.theme.text; opacity: app.logActivity
        }
        Cell {
            x: dashboard.cw * 2; y: dashboard.rh * dashboard.eventRow
            width: Math.max(0, logTools.x - x - dashboard.cw)
            text: " EVENTS " + terminalLog.count + " "; font.bold: true
            Rectangle { anchors.fill: parent; color: app.theme.base; z: -1 }
        }
        Rectangle {
            x: logTools.x; y: logTools.y; width: logTools.width; height: logTools.height
            color: app.theme.base
        }
        Row {
            id: logTools
            anchors.right: parent.right; anchors.rightMargin: dashboard.cw * 2; y: dashboard.rh * dashboard.eventRow
            spacing: dashboard.cw
            RetroButton { objectName: "guideToggle"; text: "指引"; implicitHeight: dashboard.rh; onClicked: detailPopup.open() }
            RetroButton { text: "复制"; implicitHeight: dashboard.rh; onClicked: backend.copyLogs() }
            RetroButton { text: "诊断 ZIP"; implicitHeight: dashboard.rh; enabled: !s.busy && !s.capturing && !backend.confirmation.open; onClicked: backend.exportDiagnostics() }
        }
        ListView {
            id: terminalLog; objectName: "terminalLog"
            x: dashboard.cw * 2; y: dashboard.rh * (dashboard.eventRow + 1)
            width: dashboard.cw * (app.gridColumns - 4); height: dashboard.rh * Math.max(1, app.gridRows - dashboard.eventRow - 4)
            clip: true; model: backend.logModel; activeFocusOnTab: true; keyNavigationEnabled: true; boundsBehavior: Flickable.StopAtBounds
            highlight: Rectangle { color: terminalLog.activeFocus ? app.theme.hover : "transparent" }
            ScrollBar.vertical: ScrollBar {}
            function followLatest() {
                if (!app.followLogs || count === 0) return;
                currentIndex = count - 1;
                positionViewAtEnd();
                if (currentItem && currentItem.height > height) positionViewAtIndex(currentIndex, ListView.Beginning);
            }
            function openCurrent() { if (currentItem) { app.currentRecord = currentItem.fullText; logTyper.finish(); recordPopup.open() } }
            Keys.onReturnPressed: function(event) { openCurrent(); event.accepted = true }
            Keys.onEnterPressed: function(event) { openCurrent(); event.accepted = true }
            onCountChanged: if (app.followLogs) Qt.callLater(function() { terminalLog.followLatest() })
            delegate: RetroLogLine {
                required property int index
                width: terminalLog.width - 12; colors: app.theme; fontFamily: app.font.family; rowHeight: app.cellHeight
                frame: app.motion ? app.logFrame : 0; typingSequence: logTyper.sequence; typingText: logTyper.visibleText
                onHeightChanged: if (app.followLogs) Qt.callLater(function() { terminalLog.followLatest() })
                onSelected: { logTyper.finish(); terminalLog.currentIndex = index; terminalLog.forceActiveFocus() }
                onOpened: terminalLog.openCurrent()
            }
        }
        Cell {
            visible: terminalLog.count === 0; x: dashboard.cw * 2; y: dashboard.rh * (dashboard.eventRow + 1)
            width: dashboard.cw * (app.gridColumns - 4); text: "选择 [1] 添加账号，Enter 开始。"; color: app.theme.muted
        }
        Cell {
            objectName: "terminalPrompt"; x: dashboard.cw * 2; y: dashboard.rh * (app.gridRows - 3)
            width: dashboard.cw * (app.gridColumns - 4)
            text: "> " + (app.softNotice || ((s.error ? s.error + " / " : "") + (s.notice || "")))
            Accessible.name: text
        }
        Cell {
            x: dashboard.cw * 2; y: dashboard.rh * (app.gridRows - 2)
            width: dashboard.cw * (app.gridColumns - 4); text: app.keyHints; color: app.theme.muted
        }
    }
    Column {
        visible: app.tooSmall; anchors.centerIn: parent; spacing: 12
        LabelText { text: "请放大窗口"; anchors.horizontalCenter: parent.horizontalCenter }
        SmallText { text: "至少 60×22 字符（当前 " + app.gridColumns + "×" + app.gridRows + "）" }
        Row {
            spacing: 8
            RetroButton { text: "说明"; onClicked: settings.open() }
            RetroButton { text: "恢复网络"; enabled: !s.blocked; onClicked: backend.action("desktop-recover") }
            RetroButton { text: "停止"; visible: !!s.capturing || (!!s.running && s.jobKind !== "submit"); enabled: !s.busy; onClicked: backend.action(s.capturing ? "desktop-recover" : "stop-job") }
        }
    }
    SlidePopup {
        id: introPopup; objectName: "introPopup"; restoreTaskFocus: true
        width: Math.min(760, app.width - 32); height: Math.min(630, app.height - 32); padding: app.tiny ? 16 : 24
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        background: Frame { border.color: app.theme.muted }
        Overlay.modal: Rectangle { color: app.theme.scrim }
        contentItem: ColumnLayout {
            spacing: 18
            RowLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: app.tiny ? 12 : 24
                LabelText {
                    text: " ### \n ### \n ### \n     \n ### "
                    Layout.preferredWidth: 60; Layout.alignment: Qt.AlignTop
                    lineHeightMode: Text.FixedHeight; lineHeight: 20; color: app.theme.text
                }
                ScrollView {
                    id: introScroll; Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumWidth: 0
                    clip: true; contentWidth: availableWidth
                    ColumnLayout {
                        width: introScroll.availableWidth; spacing: 14
                        LabelText { text: backend.tutorial.title; font.pixelSize: 24; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap }
                        SmallText { text: backend.tutorial.intro; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap }
                        Repeater {
                            model: backend.tutorial.steps
                            ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true; spacing: 4
                                LabelText { text: parent.modelData.title; color: parent.modelData.important ? app.theme.warning : app.theme.text; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap }
                                LabelText { text: parent.modelData.body; color: parent.modelData.important ? app.theme.warning : app.theme.muted; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap }
                            }
                        }
                        SmallText { text: backend.tutorial.tip; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap }
                        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: app.theme.line }
                        LabelText { text: "免费提供 · 源码公开"; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        SmallText { text: backend.tutorial.disclaimer; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap }
                        SmallText { text: backend.tutorial.attribution; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap }
                    }
                }
            }
            GridLayout {
                Layout.fillWidth: true; columns: introPopup.availableWidth >= 560 ? 2 : 1
                columnSpacing: 16; rowSpacing: 10
                SmallText {
                    objectName: "tutorialReopenHint"
                    text: "以后可在「说明 / 设置 → 快速上手」重新打开。"
                    Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap
                }
                RetroButton {
                    objectName: "tutorialDone"; text: "知道了，开始"; Layout.alignment: Qt.AlignRight
                    onClicked: { backend.tutorialRead(); introPopup.close() }
                }
            }
        }
        onOpened: Qt.callLater(function() { introScroll.forceActiveFocus() })
    }
    SlidePopup {
        id: detailPopup
        width: Math.min(660, app.width - 32); height: Math.min(480, app.height - 32); padding: 20
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        background: Frame {}
        Overlay.modal: Rectangle { color: app.theme.scrim }
        contentItem: ColumnLayout {
            LabelText { text: app.guideTitle; font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap }
            ScrollView {
                id: detailScroll; Layout.fillWidth: true; Layout.fillHeight: true; contentWidth: availableWidth; clip: true
                LabelText {
                    width: detailScroll.availableWidth; wrapMode: Text.Wrap
                    text: app.stepReason || (app.guideHint + (app.step === 1 ? "\n\n先点获取账号，按电脑弹窗授权。倒计时内，在「数体智慧体育」小程序里登录本人账号一次。不是登录微信，也不用重启小程序。\n\n找到账号后停留，等信息保存、网络恢复就好。" : "")) + "\n\n当前阶段：" + (s.stage || "等待操作") + "\n" + (s.notice || "") + "\n\n" + backend.tutorial.disclaimer + "\n" + backend.tutorial.attribution
                }
            }
            Check { id: followLog; objectName: "followLog"; text: "自动跟随新记录"; checked: app.followLogs; onToggled: app.followLogs = checked }
            RetroButton { text: "返回 / Esc"; onClicked: detailPopup.close() }
        }
    }
    SlidePopup {
        id: recordPopup
        width: Math.min(720, app.width - 32); height: Math.min(450, app.height - 32); padding: 20
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        background: Frame {}
        Overlay.modal: Rectangle { color: app.theme.scrim }
        contentItem: ColumnLayout {
            LabelText { text: "EVENT / 完整记录"; font.bold: true }
            ScrollView {
                id: recordScroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
                TextArea { id: recordText; text: app.currentRecord; width: recordScroll.availableWidth; readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.Wrap; color: app.theme.text; font.family: app.font.family; font.pixelSize: 20; background: null }
            }
            RetroButton { text: "返回 / Esc"; onClicked: recordPopup.close() }
        }
    }
    Timer { id: softNoticeTimer; interval: 3200; onTriggered: app.softNotice = "" }
    Item { objectName: "reopenNotice"; visible: app.softNotice !== ""; width: 0; height: 0 }

    SlidePopup {
        id: settings; objectName: "terminalSettings"
        width: Math.min(730, app.width - 32); height: Math.min(640, app.height - 32); padding: app.tiny ? 16 : 24
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        Overlay.modal: Rectangle { color: app.theme.scrim }
        background: Frame { border.color: app.theme.muted }
        contentItem: ColumnLayout {
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "设置与说明"; font.pixelSize: 20 }
                Item { Layout.fillWidth: true }
                RetroButton { text: "返回"; implicitHeight: 32; animate: app.motion; onClicked: settings.close() }
            }
            ScrollView {
                id: settingsScroll; Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: settingsScroll.availableWidth; spacing: 18
                    GridLayout {
                        Layout.fillWidth: true; columns: app.tiny ? 2 : 3; rowSpacing: 8
                        Check { objectName: "terminalMotion"; text: "界面动效"; checked: app.motion; onToggled: app.motion = checked }
                        Check { objectName: "stepSoundToggle"; text: "步骤提示音"; checked: app.stepSound; onToggled: app.stepSound = checked }
                        RetroButton { objectName: "resetAccounts"; text: "重置账号"; danger: true; animate: app.motion; enabled: !s.blocked && !s.recoveryPending; onClicked: { settings.close(); resetDialog.open() } }
                    }
                    GridLayout {
                        Layout.fillWidth: true; columns: app.tiny ? 2 : 4; columnSpacing: 8; rowSpacing: 6
                        RetroButton { objectName: "reopenTutorial"; text: "快速上手"; animate: app.motion; onClicked: { settings.close(); introPopup.open() } }
                        RetroButton { text: "项目许可"; animate: app.motion; onClicked: helpText.text = backend.document("LICENSE") + "\n" + backend.document("NOTICE") }
                        RetroButton { text: "Qt 许可"; animate: app.motion; onClicked: helpText.text = backend.document("third_party/desktop/qt/PROVENANCE.md") }
                        RetroButton { text: "字体许可"; animate: app.motion; onClicked: helpText.text = backend.document("third_party/desktop/fonts/FUSION-PIXEL.md") + "\n\n" + backend.document("third_party/desktop/fonts/FusionPixel-OFL.txt") }
                    }
                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: app.theme.line }
                    TextArea {
                        id: helpText; Layout.fillWidth: true
                        text: "1–5 / Up / Down 选择任务，Enter 执行选中任务。\n鼠标点击任务只选择，再点执行。\nTab / Shift+Tab 切换焦点，按钮 Enter / Space 操作。\nF1 说明，Esc 返回或取消；不会提交。\n\n日志中 Up / Down 选择，Enter 看完整记录。\n指引查看当前步骤完整提示；下拉框与表单不响应全局数字键。\n80×24 字符为完整布局，60×22 为单栏下限。\n这是免环境桌面仿终端，无需输入指令。\n\n仅使用本人已授权账号。记录由模板生成，非实际运动采集；不自动提交，结果不明不自动重试。\n\n原作者 dan-cun · github.com/dan-cun/lepao3\nLRL-1.0 非商业研究许可。Qt / PySide / Shiboken 保留各自许可。"
                        readOnly: true; selectByMouse: true; textFormat: TextEdit.PlainText; wrapMode: TextEdit.Wrap
                        color: app.theme.text; font.family: app.font.family; font.pixelSize: 20; background: null
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                RetroButton { text: "恢复网络并退出"; animate: app.motion; enabled: !s.blocked; onClicked: backend.action("desktop-exit") }
            }
        }
    }
    SlidePopup {
        id: registration; objectName: "registration"; restoreTaskFocus: true
        width: Math.min(460, app.width - 32); height: Math.min(390, app.height - 32); padding: 24
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        Overlay.modal: Rectangle { color: app.theme.scrim }
        background: Frame { border.color: app.theme.line }
        onOpened: personName.forceActiveFocus()
        contentItem: ColumnLayout {
            spacing: 16
            ScrollView {
                id: registrationScroll; Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: registrationScroll.availableWidth; spacing: 16
                    LabelText { text: "添加账号"; font.pixelSize: 30; font.weight: Font.DemiBold }
                    Field { id: personName; objectName: "personName"; Layout.fillWidth: true; placeholderText: "姓名或别名"; maximumLength: 40; Accessible.name: "姓名或别名" }
                    LabelText { text: "学号（必须准确）"; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Field { id: student; objectName: "studentNumber"; Layout.fillWidth: true; placeholderText: "和小程序里一致，别漏掉开头的0"; maximumLength: 32; Accessible.name: "学号（必须准确）"; onAccepted: if (registerButton.enabled) registerButton.clicked() }
                    SmallText { text: s.error ? s.notice : ""; visible: !!s.error; color: app.theme.error; Layout.fillWidth: true; wrapMode: Text.Wrap }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                RetroButton { text: "取消"; animate: app.motion; onClicked: registration.close() }
                Item { Layout.fillWidth: true }
                RetroButton { id: registerButton; objectName: "registerButton"; text: s.busy ? "添加中" : "添加"; primary: true; animate: app.motion; enabled: !!personName.text.trim() && !!student.text.trim() && !s.blocked; onClicked: backend.register(personName.text, student.text) }
            }
        }
    }
    SlidePopup {
        id: resetDialog; objectName: "resetDialog"
        width: Math.min(450, app.width - 32); height: Math.min(376, app.height - 32); padding: 24
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        Overlay.modal: Rectangle { color: app.theme.scrim }
        background: Frame { border.color: app.theme.warning }
        onOpened: resetAck.checked = false
        contentItem: ColumnLayout {
            spacing: 18
            ScrollView {
                id: resetScroll; Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: resetScroll.availableWidth; spacing: 18
                    LabelText { text: "重置账号"; font.pixelSize: 30; font.weight: Font.DemiBold }
                    SmallText { text: "清空本机登记和凭证。证书、网络恢复记录、提交账本保留。原配置在本机私有目录备份，不会导出。"; Layout.fillWidth: true; wrapMode: Text.Wrap; lineHeight: 1.5 }
                    Check { id: resetAck; objectName: "resetAck"; text: "确认重置账号，需要重新登记和获取"; Layout.fillWidth: true }
                    SmallText { text: s.error ? s.notice : ""; visible: !!s.error; color: app.theme.error; Layout.fillWidth: true; wrapMode: Text.Wrap }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                RetroButton { text: "取消"; animate: app.motion; onClicked: resetDialog.close() }
                Item { Layout.fillWidth: true }
                RetroButton { objectName: "confirmReset"; text: "确认重置"; danger: true; animate: app.motion; enabled: resetAck.checked && !s.blocked && !s.recoveryPending; onClicked: backend.resetAccounts(resetAck.checked) }
            }
        }
    }
    SlidePopup {
        id: confirmation; objectName: "submissionConfirmation"
        width: Math.min(590, app.width - 32); height: Math.min(620, app.height - 32); padding: app.tiny ? 20 : 28
        modal: true; focus: true; closePolicy: Popup.CloseOnEscape
        visible: backend.confirmation.open
        onClosed: if (backend.confirmation.open) backend.cancelConfirmation()
        onOpened: { sourceAck.checked = false; ownerAck.checked = false; cancelSubmission.forceActiveFocus() }
        Overlay.modal: Rectangle { color: app.theme.scrim }
        background: Frame { border.color: app.theme.warning }
        contentItem: ColumnLayout {
            spacing: 16
            ScrollView {
                id: confirmationScroll; Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: confirmationScroll.availableWidth; spacing: 16
                    LabelText { text: "确认提交"; font.pixelSize: 30; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    LabelText { text: (backend.confirmation.name || "") + "  /  " + (backend.confirmation.member || ""); color: app.accent; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 80; color: app.theme.overlay; radius: 0
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 12; spacing: 12
                            Metric { value: String((backend.confirmation.preview || {}).distance || 0) + " km"; caption: "只读样本距离"; Layout.fillWidth: true }
                            Metric { value: String((backend.confirmation.preview || {}).used_time || 0) + " s"; caption: "只读样本用时"; Layout.fillWidth: true }
                            Metric { value: String((backend.confirmation.preview || {}).points || 0); caption: "样本点数"; Layout.fillWidth: true }
                        }
                    }
                    LabelText { text: "模板生成，非实际运动采集。提交时重新生成，样本仅供参考。"; color: app.theme.warning; Layout.fillWidth: true; wrapMode: Text.Wrap; lineHeight: 1.5 }
                    SmallText { text: "将上传文件并提交。受理不等于有效；结果不明先核查，不自动重试。写入中请勿强退。"; Layout.fillWidth: true; wrapMode: Text.Wrap; lineHeight: 1.5 }
                    Check { id: sourceAck; objectName: "sourceAck"; text: "我理解并非实际运动采集，只在获许可的测试范围提交。"; Layout.fillWidth: true }
                    Check { id: ownerAck; objectName: "ownerAck"; text: "已核对本人账号，同意单次写入及结果不明时禁止重试。"; Layout.fillWidth: true }
                }
            }
            SmallText { text: "剩余 " + backend.confirmation.seconds + " 秒 · 取消或过期不提交"; color: app.theme.warning; Layout.fillWidth: true; wrapMode: Text.Wrap }
            GridLayout {
                id: confirmationActions
                Layout.fillWidth: true; columns: confirmation.availableWidth < 460 ? 1 : 3; columnSpacing: 10; rowSpacing: 8
                RetroButton { id: cancelSubmission; objectName: "cancelSubmission"; text: "取消，不提交"; Layout.fillWidth: confirmationActions.columns === 1; animate: app.motion; onClicked: backend.cancelConfirmation() }
                Item { visible: confirmationActions.columns === 3; Layout.fillWidth: true }
                RetroButton { objectName: "commitSubmission"; text: "确认上传并提交一次"; Layout.fillWidth: confirmationActions.columns === 1; danger: true; animate: app.motion; enabled: sourceAck.checked && ownerAck.checked && backend.confirmation.seconds > 0; onClicked: backend.commit(sourceAck.checked, ownerAck.checked) }
            }
        }
    }
}
