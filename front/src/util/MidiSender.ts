// use web midi api to send midi messages

export async function createMidiSender(): Promise<MidiSender> {
    const midi = await navigator.requestMIDIAccess();
    return new MidiSender(midi);
}

const NOTE_ON = 0x90;
const NOTE_OFF = 0x80;
const CONTROL_CHANGE = 0xB0;
const PITCH_BEND = 0xE0;

export class MidiSender {
    public midi: MIDIAccess;
    private outPort: MIDIOutput | null = null;
    public noteOnCallback: (note: number, velocity: number, channel: number) => void = () => {};
    public noteOffCallback: (note: number, channel: number) => void = () => {};
    public controlChangeCallback: (control: number, value: number, channel: number) => void = () => {};
    public pitchBendCallback: (value: number, channel: number) => void = () => {};
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

    sendNoteOn(note: number, velocity: number, channel: number = 1) {
        if (channel < 1 || channel > 16) {
            console.error('Invalid channel', channel);
            return;
        }
        if (!this.outPort) return console.error('No output port selected');
        this.outPort.send([NOTE_ON + channel - 1, note, velocity]);
        this.noteOnCallback(note, velocity, channel);
    }

    sendNoteOff(note: number, channel: number = 1) {
        if (channel < 1 || channel > 16) {
            console.error('Invalid channel', channel);
            return;
        }
        if (!this.outPort) return console.error('No output port selected');
        this.outPort.send([NOTE_OFF + channel - 1, note, 0]);
        this.noteOffCallback(note, channel);
    }

    sendControlChange(control: number, value: number, channel: number = 1) {
        if (channel < 1 || channel > 16) {
            console.error('Invalid channel', channel);
            return;
        }
        if (!this.outPort) return console.error('No output port selected');
        value = Math.round(value);
        if (value < 0) {
            value = 0;
        }
        if (value > 127) {
            value = 127;
        }
        this.outPort.send([CONTROL_CHANGE + channel - 1, control, value]);
        this.controlChangeCallback(control, value, channel);
    }
    /*
    Pitch bend is a 14-bit value, where 0 is the center, -8192 is the minimum, and 8191 is the maximum.
    We need to convert it to a 7-bit value, where 0 is the center, and 127 is the maximum.
    */
    sendPitchBend(value: number, channel: number = 1) {
        if (channel < 1 || channel > 16) {
            console.error('Invalid channel', channel);
            return;
        }

        // limit to -8192 to 8191
        value = Math.round(value);
        if (value < -8192) {
            value = -8192;
        }
        if (value > 8191) {
            value = 8191;
        }
        if (!this.outPort) return console.error('No output port selected');
        const unsignedValue = value + 8192;
        const lsb = unsignedValue & 0x7F; // lower 7 bits
        const msb = (unsignedValue >> 7) & 0x7F; // upper 7 bits
        this.outPort.send([PITCH_BEND + channel - 1, lsb, msb]);
        this.pitchBendCallback(value, channel);
    }
}
