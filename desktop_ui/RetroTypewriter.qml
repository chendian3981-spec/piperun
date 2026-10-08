// pipeRun derivative · dan-cun / github.com/dan-cun/lepao3 · LRL-1.0, noncommercial research.
import QtQuick

Item {
    id: typer
    width: 0; height: 0
    property bool animate: true
    property int lastSequence: -1
    property int sequence: -1
    property var glyphs: []
    property int revealed: 0
    readonly property string visibleText: glyphs.slice(0, revealed).join("")
    readonly property int intervalMs: 24
    readonly property int maximumTicks: 24

    function finish() {
        tick.stop();
        sequence = -1;
        glyphs = [];
        revealed = 0;
    }
    function receive(entries, initial) {
        if (!entries || entries.length === 0) return;
        var latest = entries[entries.length - 1];
        if (latest.seq <= lastSequence) return;
        lastSequence = latest.seq;
        // Bursts finalize previous lines immediately instead of delaying a log queue.
        finish();
        if (initial || !animate || latest.level === "ERROR" || latest.level === "WARN") return;
        // Catalog log text is plain text; code points avoid splitting surrogate pairs.
        glyphs = Array.from(String(latest.text || ""));
        sequence = latest.seq;
        tick.restart();
    }
    onAnimateChanged: if (!animate) finish()
    Timer {
        id: tick
        interval: typer.intervalMs; repeat: true
        onTriggered: {
            typer.revealed = Math.min(typer.glyphs.length,
                typer.revealed + Math.max(1, Math.ceil(typer.glyphs.length / typer.maximumTicks)));
            if (typer.revealed >= typer.glyphs.length) typer.finish();
        }
    }
}
