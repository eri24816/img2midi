import { MidiSender } from './MidiSender';

const CONTROL_MAP = {
    'intensity': {
        'control': 11,
        'sourceMin': 0,
        'sourceMax': 1,
    },
    'density': {
        'control': 75,
        'sourceMin': 0,
        'sourceMax': 1,
    },
    'pitch': {
        'control': 76,
        'sourceMin': -4,
        'sourceMax': 4,
    },
    'hue': {
        'control': 77,
        'sourceMin': 0,
        'sourceMax': 140,
    },
    'saturation': {
        'control': 78,
        'sourceMin': 0,
        'sourceMax': 1,
    },
    'value': {
        'control': 79,
        'sourceMin': 0,
        'sourceMax': 1,
    },
}

type ControlKey = keyof typeof CONTROL_MAP;

export class ImagePlayer {
    private parameters: Map<string, Float32Array>;
    private midiSender: MidiSender;
    private time: number = 0;
    private length: number = 0;
    private timeScale: number = 8.333;

    constructor() {
    }
    
    async play(parameters: Map<string, Float32Array>, midiSender: MidiSender, length: number, timeScale: number = 8.333) {
        this.timeScale = timeScale*8.333/100;

        this.parameters = parameters;
        this.midiSender = midiSender;
        this.time = 0;
        this.length = length;
        let noteOnSent = false;
        while (true) {
            const idx = Math.floor(this.time * this.timeScale);
            if (idx >= this.length) {
                this.midiSender.sendNoteOff(60);
                break;
            }
            for (const [key, value] of this.parameters.entries()) {
                if (!(key in CONTROL_MAP)) {
                    continue;
                }
                const controlKey = key as ControlKey;
                const control = CONTROL_MAP[controlKey].control;
                const sourceMin = CONTROL_MAP[controlKey].sourceMin;
                const sourceMax = CONTROL_MAP[controlKey].sourceMax;
                const targetMin = 0
                const targetMax = 127
                let targetValue = (value![idx] - sourceMin) / (sourceMax - sourceMin) * (targetMax - targetMin) + targetMin;
                
                this.midiSender.sendControlChange(control, targetValue);
            }

            if (!noteOnSent) {
                this.midiSender.sendNoteOn(60, 127);
                noteOnSent = true;
            }

            this.time += 1/this.timeScale;
            await new Promise(resolve => setTimeout(resolve, 1000/this.timeScale));
        }
    }

    
}
