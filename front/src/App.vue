<template>
    <div>
        <h1>img2midi</h1>
        
        <div class="midi-section">
            <label for="midiInput">MIDI Input Port:</label>
            <select 
                id="midiInput" 
                v-model="selectedInput"
                @change="handleInputChange"
            >
                <option 
                    v-for="input in midiInputs" 
                    :key="input.id" 
                    :value="input.id"
                >
                    {{ input.name }}
                </option>
            </select>
            <br>
            <br>
            <label for="midiOutput">MIDI Output Port:</label>
            <select 
                id="midiOutput" 
                v-model="selectedOutput"
                @change="handleOutputChange"
            >
                <option 
                    v-for="output in midiOutputs" 
                    :key="output.id" 
                    :value="output.id"
                >
                    {{ output.name }}
                </option>
            </select>
        </div>

        <div class="setting">
            <label for="timeScale">Pixels per second (playback speed)</label>
            <RangedInput id="timeScale" v-model="timeScale" :min="20" :max="1000" :step="20" />
        </div>

        <div class="setting">
            <label for="pixelsPerSemitone">Pixels per semitone</label>
            <RangedInput id="pixelsPerSemitone" v-model="pixelsPerSemitone" :min="10" :max="400" :step="10" />
        </div>

        <div class="setting">
            <label for="channels">Output channels</label>
            <RangedInput id="channels" v-model="channels" :min="1" :max="16" :step="1" />
        </div>

        <div class="setting">
            <label for="pitchVariationFactor">Pitch variation factor</label>
            <RangedInput id="pitchVariationFactor" v-model="pitchVariationFactor" :min="0" :max="1" :step="0.01" />
        </div>

        <button @click="handleTest">Test</button>

        Upload image:
        <input type="file" @change="handleFileUpload" accept="image/*">
        
        <div class="columns">
            <div class="column">
                <table class="image-table">
                    <tr>
                        <th>Play</th>
                        <th>Image</th>
                        <th>Image size</th>
                        <th>Duration</th>
                    </tr>
                    <tr v-for="item in uploadedImages.values()" :key="item.id">
                        <td>
                            <button 
                                @click="playImage(item)"
                                :disabled="!item.strokes"
                                class="play-button"
                            >
                                {{ item.strokes ? 'Play' : 'Analyzing...' }}
                            </button>
                        </td>
                        <td><img :src="item.imageUrl" width="200" /></td>
                        <td>
                            {{ item.dimensions.width }} x {{ item.dimensions.height }} pixels
                        </td>
                        <td>
                            {{ (item.dimensions.width / timeScale).toFixed(2) }} seconds
                        </td>
                    </tr>
                </table>
            </div>
            <div class="column">
                MIDI output:
                <div v-for="(message, index) in midiOutLog" :key="index">
                    {{ message }}
                </div>
            </div>
            <div class="column">
                MIDI input:
                <div v-for="(message, index) in midiInLog" :key="index">
                    {{ message }}
                </div>
            </div>
        </div>
        <Footer />
    </div>
</template>

<script setup lang="ts"> 
import { ref, onMounted, watch } from 'vue';
import { createMidiSender, MidiSender } from './util/MidiSender';
import { ImagePlayer, MultiImagePlayer } from './util/ImagePlayer';
import { Base64Binary } from './util/base64-binary';
import Footer from './Footer.vue';
import RangedInput from './components/RangedInput.vue';
interface ImageItem {
    id: number;
    imageUrl: string;
    dimensions: {width: number, height: number};
    strokes?: StrokeInfo<Float32Array>[];
}
type AnalyzeResponse = StrokeInfo<number[]>[];

interface StrokeInfo<ParamT> {
    length: number;
    start_x: number;
    start_y: number;
    end_x: number;
    end_y: number;
    parameters: {// base64 encoded float32 arrays
        intensity: ParamT;
        pos_y: ParamT;
        density: ParamT;
        hue: ParamT;
        saturation: ParamT;
        value: ParamT;
        pos_x: ParamT;
    }
}

const midiInputs = ref<{id: string, name: string}[]>([]);
const selectedInput = ref<string | null>(null);
const midiOutputs = ref<{id: string, name: string}[]>([]);
const selectedOutput = ref<string | null>(null);
const uploadedImages = ref<Map<number, ImageItem>>(new Map());
const midiOutLog = ref<string[]>([]);
const midiInLog = ref<string[]>([]);
const timeScale = ref<number>(100);
const pixelsPerSemitone = ref<number>(50);
const channels = ref<number>(16);
const player = new MultiImagePlayer();
const pitchVariationFactor = ref<number>(1);

let midiSender: MidiSender | null = null;

const handleOutputChange = () => {
    if (midiSender && selectedOutput.value) {
        midiSender.setOutPort(selectedOutput.value);
    }
}

const handleInputChange = () => {
    if (midiSender && selectedInput.value) {
        midiSender.setInPort(selectedInput.value);
    }
}

const handleFileUpload = async (event: Event) => {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;

    // Create URL for image display
    const imageUrl = URL.createObjectURL(file);
    
    // Create temporary image to get dimensions
    const img = new Image();
    img.onload = () => {
        // Add to images array with dimensions
        const newItem: ImageItem = { 
            imageUrl, 
            id: Math.random(), 
            dimensions: {
                width: img.naturalWidth,
                height: img.naturalHeight
            }
        };
        uploadedImages.value.set(newItem.id, newItem);

        // Convert to base64
        const reader = new FileReader();
        reader.onload = async () => {
            const base64Data = (reader.result as string).split(',')[1];

            try {
                // Send to backend
                const response = await fetch('/api/analyze-notation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: base64Data })
                });
                
                const responseJson: AnalyzeResponse = await response.json();
                function convertStrokeToFloat32Array(stroke: StrokeInfo<number[]>): StrokeInfo<Float32Array> {
                    const result: StrokeInfo<Float32Array> = {
                        ...stroke,
                        parameters: Object.fromEntries(
                            Object.entries(stroke.parameters).map(([key, value]) => [key, new Float32Array(value)])
                        ) as StrokeInfo<Float32Array>['parameters']
                    };
                    return result;
                }
                const strokes = responseJson.map(convertStrokeToFloat32Array);
                uploadedImages.value.get(newItem.id).strokes = strokes;
            } catch (error) {
                console.error('Analysis failed:', error);
            }
        };
        reader.readAsDataURL(file);
    };
    img.src = imageUrl;
}

const playImage = async (item: ImageItem) => {
    if (!item.strokes) return;
    // TODO: Implement playback using parameters
    for (const stroke of item.strokes) {
        const pitch = 55 + Math.round(stroke.start_y / pixelsPerSemitone.value);
        const posYShift = - Math.round(stroke.start_y / pixelsPerSemitone.value) * pixelsPerSemitone.value;
        const time = stroke.start_x / timeScale.value;
        const semitonePerPixelForVariation = pitchVariationFactor.value / pixelsPerSemitone.value;
        setTimeout(() => {
            player.play(stroke.parameters, midiSender, stroke.length, pitch, timeScale.value, semitonePerPixelForVariation, posYShift);
        }, time* 1000);
    }
}

onMounted(async () => {
    midiSender = await createMidiSender();
    const inPorts = midiSender.getInputs();
    for (const input of inPorts) {
        midiInputs.value.push({
            id: input[0],
            name: input[1].name || '',
        });
    }
    if (midiInputs.value.length > 0) {
        selectedInput.value = midiInputs.value[0].id;
        handleInputChange();
    }
    const outPorts = midiSender.getOutputs();
    for (const output of outPorts) {
        midiOutputs.value.push({
            id: output[0],
            name: output[1].name || '',
        });
    }
    if (midiOutputs.value.length > 0) {
        selectedOutput.value = midiOutputs.value[0].id;
        handleOutputChange();
    }
    midiSender.inNoteOnCallback = handleInNoteOn;
    midiSender.inNoteOffCallback = handleInNoteOff;
    midiSender.inControlChangeCallback = handleInControlChange;
    midiSender.inPitchBendCallback = handleInPitchBend;
    midiSender.inUnknownCallback = handleInUnknown;

    midiSender.outNoteOnCallback = handleOutNoteOn;
    midiSender.outNoteOffCallback = handleOutNoteOff;
    midiSender.outControlChangeCallback = handleOutControlChange;
    midiSender.outPitchBendCallback = handleOutPitchBend;
});

const handleInNoteOn = (note: number, velocity: number, channel: number) => {
    midiInLog.value.push(`note on ${channel} ${note} ${velocity}`);
    trimMidiLog();
}

const handleInNoteOff = (note: number, channel: number) => {
    midiInLog.value.push(`note off ${channel} ${note}`);
    trimMidiLog();
}

const handleInControlChange = (control: number, value: number, channel: number) => {
    midiInLog.value.push(`control change ${channel} ${control} ${value}`);
    trimMidiLog();
}

const handleInPitchBend = (value: number, channel: number) => {
    midiInLog.value.push(`pitch bend ${channel} ${value}`);
    trimMidiLog();
}

const handleInUnknown = (status: number, message: number[]) => {
    midiInLog.value.push(`unknown ${status} ${message}`);
    trimMidiLog();
}

const handleOutNoteOn = (note: number, velocity: number, channel: number) => {
    midiOutLog.value.push(`note on ${channel} ${note} ${velocity}`);
    trimMidiLog();
}

const handleOutNoteOff = (note: number, channel: number) => {
    midiOutLog.value.push(`note off ${channel} ${note}`);
    trimMidiLog();
}

const handleOutControlChange = (control: number, value: number, channel: number) => {
    midiOutLog.value.push(`control change ${channel} ${control} ${value}`);
    trimMidiLog();
}

const handleOutPitchBend = (value: number, channel: number) => {
    midiOutLog.value.push(`pitch bend ${channel} ${value}`);
    trimMidiLog();
}

const trimMidiLog = () => {
    midiOutLog.value = midiOutLog.value.slice(-10);
    midiInLog.value = midiInLog.value.slice(-10);
}

watch(channels, (newChannels) => {
    player.setChannels(Array.from({length: newChannels}, (_, i) => i + 1)); // from 1 to newChannels
});

const handleTest = async () => {
    // send pitch bend -8192 to 8191 with 2ms interval
    // midiSender.sendNoteOn(60, 127, 1);
    // for (let i = -8192; i <= 8191; i++) {
    //     midiSender.sendPitchBend(i, 1);
    //     await new Promise(resolve => setTimeout(resolve, 2));
    // }
    // midiSender.sendNoteOff(60, 1);
}
</script>

<style scoped>
.midi-section {
    margin-top: 20px;
    margin-bottom: 20px;
}

select {
    margin-left: 10px;
    padding: 5px;
    min-width: 200px;
}

.image-table {
    margin-top: 20px;
    border-collapse: collapse;
}

.image-table td {
    padding: 10px;
    border: 1px solid #ddd;
}

.play-button {
    padding: 8px 16px;
    cursor: pointer;
}

.play-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.columns {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
}

.column {
    margin: 10px;
}

footer {
    text-align: center;
    background-color: #000000;
    position: fixed;
    bottom: 0;
    width: 100%;
    height: 60px;
}

.setting {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    gap: 10px;
    margin-top: 10px;
    margin-bottom: 10px;
}

.setting label {
    min-width: 250px;
}
</style>