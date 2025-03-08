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
    'hue': {
        'control': 77,
        'sourceMin': 0,
        'sourceMax': 1,
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

export class MultiImagePlayer {
    private players: ImagePlayer[] = [];
    private channels: number[] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];

    setChannels(channels: number[]) {
        this.channels = channels;
    }

    getOneFreeChannel(allowedChannels: number[]|null = null): number {
        if (allowedChannels === null) {
            allowedChannels = this.channels;
        }

        const freeChannels = allowedChannels.filter(channel => !this.players.some(player => player.channel === channel));
        if (freeChannels.length === 0) {
            // kick player with the lowest remaining time
            let kickedPlayer: ImagePlayer | null = null;
            for (const player of this.players) {
                if (!kickedPlayer || player.getRemainingTime() < kickedPlayer.getRemainingTime()) {
                    kickedPlayer = player;
                }
            }
            kickedPlayer.stop();
            this.players = this.players.filter(player => player !== kickedPlayer);
            return kickedPlayer!.channel;
        }
        return freeChannels[0];
    }

    constructor() {
    }

    play(parameters: Record<string, Float32Array>, midiSender: MidiSender, length: number, pitch: number, timeScale: number = 16.666, pitchVariationFactor: number = 1, posYShift: number = 0, allowedChannels: number[]|null = null) {
        const channel = this.getOneFreeChannel(allowedChannels);
        const player = new ImagePlayer(channel);
        this.players.push(player);
        player.play(channel, parameters, midiSender, length, pitch, timeScale, pitchVariationFactor, posYShift).then(() => {
            this.stop(player);
        });
        return () => {
            this.stop(player);
        }
    }
    
    private stop(player: ImagePlayer) {
        player.stop();
        this.players = this.players.filter(element => element !== player);
    }
}

export class ImagePlayer {
    private parameters: Record<string, Float32Array>;
    private midiSender: MidiSender;
    private time: number = 0;
    private length: number = 0;
    private timeScale: number = 16.666;
    pitch: number = 0;
    private stopped: boolean = false;
    channel: number;
    constructor(channel: number) {
        this.channel = channel;
    }

    getTime() {
        return this.time;
    }

    getRemainingTime() {
        return this.length / this.timeScale - this.time;
    }

    stop() {
        this.midiSender.sendNoteOff(this.pitch, this.channel);
        this.stopped = true;
    }
    
    async play(channel: number, parameters: Record<string, Float32Array>, midiSender: MidiSender, length: number, pitch: number, timeScale: number = 16.666, pitchVariationFactor: number = 1, posYShift: number = 0) {
        this.timeScale = timeScale*16.666/100;
        this.channel = channel;
        console.log(parameters['hue']);
        this.parameters = parameters;
        this.midiSender = midiSender;
        this.time = 0;
        this.length = length;
        this.pitch = pitch;
        let noteOnSent = false;
        while (true) {
            if (this.stopped) {
                break;
            }
            const idx = Math.floor(this.time * this.timeScale);
            if (idx >= this.length) {
                this.midiSender.sendNoteOff(pitch, this.channel);
                break;
            }
            for (const [key, value] of Object.entries(this.parameters)) {

                if (key === 'pos_y') {
                    const pitchBendSemitone = (value![idx] + posYShift) * pitchVariationFactor
                    const pitchBendValue = Math.round(pitchBendSemitone * 8192 / 12);
                    this.midiSender.sendPitchBend(pitchBendValue, this.channel);
                    continue;
                }
                

                if (!(key in CONTROL_MAP)) {
                    continue;
                }


                const controlKey = key as ControlKey;
                const control = CONTROL_MAP[controlKey].control;
                let factor = 1;
                const sourceMin = CONTROL_MAP[controlKey].sourceMin;
                const sourceMax = CONTROL_MAP[controlKey].sourceMax;
                let targetMin = 0
                let targetMax = 127
                let targetValue = (value![idx] * factor - sourceMin) / (sourceMax - sourceMin) * (targetMax - targetMin) + targetMin;

                this.midiSender.sendControlChange(control, targetValue, this.channel);
            }

            if (!noteOnSent) {
                this.midiSender.sendNoteOn(pitch, 127, this.channel);
                noteOnSent = true;
            }

            this.time += 1/this.timeScale;
            await new Promise(resolve => setTimeout(resolve, 1000/this.timeScale));
        }
    }

    
}
