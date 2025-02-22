// use web midi api to send midi messages

export async function createMidiSender(): Promise<MidiSender> {
    const midi = await navigator.requestMIDIAccess();
    return new MidiSender(midi);
}

const NOTE_ON = 0x90;
const NOTE_OFF = 0x80;
const CONTROL_CHANGE = 0xB0;

export class MidiSender {
    public midi: MIDIAccess;
    private outPort: MIDIOutput | null = null;
    public noteOnCallback: (note: number, velocity: number) => void = () => {};
    public noteOffCallback: (note: number) => void = () => {};
    public controlChangeCallback: (control: number, value: number) => void = () => {};
    constructor(midi: MIDIAccess) {
        this.midi = midi;
        for (const entry of midi.outputs) {
            const output = entry[1];
            console.log(
              `Output port [type:'${output.type}'] id: '${output.id}' manufacturer: '${output.manufacturer}' name: '${output.name}' version: '${output.version}'`,
            );
        }
        (window as any).sender = this;
    }

    getOutputs() {
        return this.midi.outputs;
    }

    setOutPort(port: string) {
        const outPorts = this.getOutputs();
        for (const output of outPorts) {
            if (output[0] === port) {
                this.outPort = output[1];
            }
        }
    }

    sendNoteOn(note: number, velocity: number) {
        if (!this.outPort) return console.error('No output port selected');
        this.outPort.send([NOTE_ON, note, velocity]);
        this.noteOnCallback(note, velocity);
    }

    sendNoteOff(note: number) {
        if (!this.outPort) return console.error('No output port selected');
        this.outPort.send([NOTE_OFF, note, 0]);
        this.noteOffCallback(note);
    }

    sendControlChange(control: number, value: number) {
        if (!this.outPort) return console.error('No output port selected');
        value = Math.round(value);
        if (value < 0) {
            value = 0;
        }
        if (value > 127) {
            value = 127;
        }
        this.outPort.send([CONTROL_CHANGE, control, value]);
        this.controlChangeCallback(control, value);
    }
}
