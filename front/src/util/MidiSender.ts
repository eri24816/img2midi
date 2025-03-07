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
    private inPort: MIDIInput | null = null;
    private outPort: MIDIOutput | null = null;
    public inNoteOnCallback: (note: number, velocity: number, channel: number) => void = () => {};
    public inNoteOffCallback: (note: number, channel: number) => void = () => {};
    public inControlChangeCallback: (control: number, value: number, channel: number) => void = () => {};
    public inPitchBendCallback: (value: number, channel: number) => void = () => {};
    public outNoteOnCallback: (note: number, velocity: number, channel: number) => void = () => {};
    public outNoteOffCallback: (note: number, channel: number) => void = () => {};
    public outControlChangeCallback: (control: number, value: number, channel: number) => void = () => {};
    public outPitchBendCallback: (value: number, channel: number) => void = () => {};
    public inUnknownCallback: (status: number, message: number[]) => void = () => {};
    public outUnknownCallback: (status: number, message: number[]) => void = () => {};
    constructor(midi: MIDIAccess) {
        this.midi = midi;
        for (const entry of midi.outputs) {
            const output = entry[1];
            console.log(
              `Output port [type:'${output.type}'] id: '${output.id}' manufacturer: '${output.manufacturer}' name: '${output.name}' version: '${output.version}'`,
            );
        }
        (window as any).sender = this;
        this.handleMidiMessage = this.handleMidiMessage.bind(this);
    }

    getInputs() {
        return this.midi.inputs;
    }

    getOutputs() {
        return this.midi.outputs;
    }

    setInPort(port: string) {
        const inPorts = this.getInputs();
        let selectedPort = null;
        for (const input of inPorts) {
            if (input[0] === port) {
                selectedPort = input[1];
            }
        }
        if (!selectedPort) return console.error('No input port selected');
        this.inPort?.removeEventListener('midimessage', this.handleMidiMessage);
        this.inPort = selectedPort;
        this.inPort.addEventListener('midimessage', this.handleMidiMessage);
    }

    setOutPort(port: string) {
        const outPorts = this.getOutputs();
        for (const output of outPorts) {
            if (output[0] === port) {
                this.outPort?.close();
                this.outPort = output[1];
            }
        }
    }
    

    handleMidiMessage(event: MIDIMessageEvent) {
        const data = event.data;
        const message = Array.from(data);
        const status = message[0];
        const note = message[1];
        const velocity = message[2];
        if (status === NOTE_ON) {
            this.inNoteOnCallback(note, velocity, 1);
        } else if (status === NOTE_OFF) {
            this.inNoteOffCallback(note, 1);
        } else if (status === CONTROL_CHANGE) {
            this.inControlChangeCallback(message[1], message[2], 1);
        } else if (status === PITCH_BEND) {
            this.inPitchBendCallback(message[1], 1);
        } else {
            this.inUnknownCallback(status, message);
        }
    }

    sendNoteOn(note: number, velocity: number, channel: number = 1) {
        if (channel < 1 || channel > 16) {
            console.error('Invalid channel', channel);
            return;
        }
        if (note < 0 || note > 127) {
            console.error('Invalid note', note);
            return;
        }
        if (!this.outPort) return console.error('No output port selected');
        this.outPort.send([NOTE_ON + channel - 1, note, velocity]);
        this.outNoteOnCallback(note, velocity, channel);
    }

    sendNoteOff(note: number, channel: number = 1) {
        if (channel < 1 || channel > 16) {
            console.error('Invalid channel', channel);
            return;
        }
        if (note < 0 || note > 127) {
            console.error('Invalid note', note);
            return;
        }
        if (!this.outPort) return console.error('No output port selected');
        this.outPort.send([NOTE_OFF + channel - 1, note, 0]);
        this.outNoteOffCallback(note, channel);
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
        this.outControlChangeCallback(control, value, channel);
    }
    /*
    Pitch bend is a 14-bit value, where 0 is the center, -8192 is the minimum, and 8191 is the maximum.
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
        this.outPitchBendCallback(value, channel);
    }
}
