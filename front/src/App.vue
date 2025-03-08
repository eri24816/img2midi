<template>
    <main>
        <h1>img2midi</h1>
        <div class="columns">
            

            <div class="settings-section">
                <div class="setting">
                    <label for="timeScale">Pixels per second (playback speed)</label>
                    <RangedInput id="timeScale" v-model="timeScale" :min="20" :max="1000" :step="20" />
                </div>

                <div class="setting">
                    <label for="pixelsPerSemitone">Pixels per semitone</label>
                    <RangedInput id="pixelsPerSemitone" v-model="pixelsPerSemitone" :min="10" :max="400" :step="10" />
                </div>

                <div class="setting">
                    <label for="pitchVariationFactor">Pitch variation factor</label>
                    <RangedInput id="pitchVariationFactor" v-model="pitchVariationFactor" :min="0" :max="1" :step="0.01" />
                </div>


                
                <div>

                    <FileInput @selected="handleFileUpload">
                        ➕ Upload image
                    </FileInput>
                    <table class="image-table">
                        <tr>
                            <th></th>
                            <th>Listen to channel</th>
                            <th>Output channels</th>
                            <th>Image</th>
                            <th>Image size</th>
                            <th>Duration</th>
                        </tr>
                        <tr v-for="item in uploadedImages.values()" :key="item.id">
                            <td>
                                <!-- <div class="select-indicator" :class="{'selected': selectedImage?.id === item.id}"></div> -->
                            
                                <button 
                                    @click="playImage(item)"
                                    :disabled="!item.strokes"
                                    class="play-button"
                                >
                                    {{ item.strokes ? 'Play' : 'Analyzing...' }}
                                </button>
                            </td>

                            <td>
                                <input type="number" :class="{'playing-image': item.isPlaying}" v-model="item.listenToChannel" :min="1" :max="16" :step="1" />
                            </td>
                            <td>
                                <CompactMultiSelect id="outputChannels" v-model="item.outputChannels" :items="outputChannels" />
                            </td>

                            <td>
                                <div style="display: flex; align-items: center;">
                                    <img :src="item.imageUrl" width="180" />
                                    <button 
                                        @click="deleteImage(item.id)" 
                                        class="delete-button"
                                        style="margin-left: 8px;"
                                    >
                                        🗑️
                                    </button>
                                </div>
                            </td>
                            
                            <td>
                                {{ item.dimensions.width }} x {{ item.dimensions.height }} pixels
                            </td>
                            <td>
                                {{ (item.dimensions.width / timeScale).toFixed(2) }} seconds
                            </td>
                        </tr>
                    </table>

                </div>
            </div>

            <div class="midi-section">
            
                <div class="midi-section-row">
                    <label for="midiInput">MIDI input port </label>
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
                    
                </div>
                <div class="midi-section-row">
                    <label for="midiInput">MIDI input channels </label>
                    <CompactMultiSelect id="midiInput" v-model="inputChannels" :items="Array.from({length: 16}, (_, i) => i + 1)" />
                </div>
                <div class="midi-section-row">
                    <label for="midiOutput">MIDI output port </label>
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
                <div class="midi-section-row">
                    <label for="midiOutput">MIDI output channels </label>
                    <CompactMultiSelect id="midiOutput" v-model="outputChannels" :items="Array.from({length: 16}, (_, i) => i + 1)" />
                </div>

                <div class="columns">
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

            </div>
        </div>
    </main>
    <Footer />
</template>

<script setup lang="ts"> 
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import { createMidiSender, MidiSender } from './util/MidiSender';
import { MultiImagePlayer } from './util/ImagePlayer';
import Footer from './Footer.vue';
import RangedInput from './components/RangedInput.vue';
import CompactMultiSelect from './components/CompactMultiSelect.vue';
import FileInput from './components/FileInput.vue';
interface ImageItem {
    id: number;
    imageUrl: string;
    dimensions: {width: number, height: number};
    listenToChannel: number;
    outputChannels: number[];
    isPlaying: boolean;
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
const inputChannels = ref<number[]>(Array.from({length: 16}, (_, i) => i + 1));
const midiOutputs = ref<{id: string, name: string}[]>([]);
const selectedOutput = ref<string | null>(null);
const outputChannels = ref<number[]>([1]);
const uploadedImages = ref<Map<number, ImageItem>>(new Map());
const midiOutLog = ref<string[]>([]);
const midiInLog = ref<string[]>([]);
const timeScale = ref<number>(100);
const pixelsPerSemitone = ref<number>(50);
const player = new MultiImagePlayer();
const pitchVariationFactor = ref<number>(1);
const selectedImage = ref<ImageItem | null>(null);
const stopHandles: Map<number, (() => void)[]> = new Map(Array.from({length: 128}, (_, i): [number, (() => void)[]] => [i, []]));

let midiSender: MidiSender | null = null;

const mapToRecord = <T>(map: Map<number, T>): Record<number, T> => {
    return Object.fromEntries(map.entries());
}

const recordToMap = <T>(record: Record<number, T>): Map<number, T> => {
    return new Map(Object.entries(record).map(([key, value]) => [Number(key), value]));
}

const saveData = async () => {
    localStorage.setItem('uploadedImages', JSON.stringify(mapToRecord(uploadedImages.value)));
    // save all image data
    const imageBase64s: Record<number, string> = {};
}

const loadData = () => {
    // localStorage.removeItem('uploadedImages');
    const savedImages = localStorage.getItem('uploadedImages');
    if (savedImages) {
        uploadedImages.value = recordToMap(JSON.parse(savedImages));
    }
}

onMounted(async () => {
    window.addEventListener("beforeunload", saveData);
    player.setChannels(outputChannels.value);
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

    loadData();
});

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

const handleFileUpload = async (file: File) => {
    if (!file) return;

    // Convert to base64 first
    const reader = new FileReader();
    reader.onload = async () => {
        const base64Data = reader.result as string;
        
        // Create temporary image to get dimensions
        const img = new Image();
        img.onload = async () => {
            // Add to images array with dimensions
            const newItem: ImageItem = { 
                imageUrl: base64Data, // Use base64 string directly
                id: Math.random(), 
                dimensions: {
                    width: img.naturalWidth,
                    height: img.naturalHeight
                },
                listenToChannel: 1,
                outputChannels: outputChannels.value.slice(0, 1),
                isPlaying: false
            };
            uploadedImages.value.set(newItem.id, newItem);

            try {
                // Send to backend - extract base64 data part
                const base64ForApi = base64Data.split(',')[1];
                const response = await fetch('/api/analyze-notation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: base64ForApi })
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
                uploadedImages.value.get(newItem.id)!.strokes = strokes;
                if(uploadedImages.value.size === 1) {
                    selectedImage.value = newItem;
                }
            } catch (error) {
                console.error('Analysis failed:', error);
            }
        };
        img.src = base64Data;
    };
    reader.readAsDataURL(file);
}

const deleteImage = (id: number) => {
    uploadedImages.value.delete(id);
}

const playImage = async (item: ImageItem, note: number=55) => {
    if (!item.strokes) return;
    let lastTime = 0;
    let playerStopHandles: (() => void)[] = [];
    let stopped = false;
    const stopHandle = () => {
        playerStopHandles.forEach(handle => handle());
        stopped = true;
    }
    stopHandles.get(note)!.push(stopHandle);
    // sort strokes by start_x
    item.strokes.sort((a, b) => a.start_x - b.start_x);
    for (const stroke of item.strokes) {
        const pitch = note + Math.max(0, Math.round(stroke.start_y / pixelsPerSemitone.value - 1));
        const posYShift = - Math.round(stroke.start_y / pixelsPerSemitone.value) * pixelsPerSemitone.value;
        const time = stroke.start_x / timeScale.value;
        const semitonePerPixelForVariation = pitchVariationFactor.value / pixelsPerSemitone.value;
        const delay = time - lastTime;
        if (delay > 0) {
            await new Promise(resolve => setTimeout(resolve, delay * 1000));
        }
        lastTime = time;
        if (stopped) break;
        playerStopHandles.push(player.play(stroke.parameters, midiSender, stroke.length, pitch, timeScale.value, semitonePerPixelForVariation, posYShift, item.outputChannels));
    }
    stopHandles.get(note)!.splice(stopHandles.get(note)!.indexOf(stopHandle), 1);
}

const handleInNoteOn = (note: number, velocity: number, channel: number) => {
    if (!inputChannels.value.includes(channel)) {
        return;
    }
    midiInLog.value.push(`note on ${channel} ${note} ${velocity}`);
    trimMidiLog();

    // get all image that listen to this channel
    const images = Array.from(uploadedImages.value.values()).filter(item => item.listenToChannel === channel);
    for (const image of images) {
        image.isPlaying = true;
        playImage(image, note);
    }
}

const handleInNoteOff = (note: number, channel: number) => {
    if (!inputChannels.value.includes(channel)) {
        return;
    }
    midiInLog.value.push(`note off ${channel} ${note}`);
    trimMidiLog();
    // get all image that listen to this channel
    const images = Array.from(uploadedImages.value.values()).filter(item => item.listenToChannel === channel);
    for (const image of images) {
        image.isPlaying = false;
        stopHandles.get(note)!.forEach(handle => handle());
    }
}

const handleInControlChange = (control: number, value: number, channel: number) => {
    if (!inputChannels.value.includes(channel)) {
        return;
    }
    midiInLog.value.push(`control change ${channel} ${control} ${value}`);
    trimMidiLog();
}

const handleInPitchBend = (value: number, channel: number) => {
    if (!inputChannels.value.includes(channel)) {
        return;
    }
    midiInLog.value.push(`pitch bend ${channel} ${value}`);
    trimMidiLog();
}

const handleInUnknown = (status: number, channel: number, message: number[]) => {
    if (!inputChannels.value.includes(channel)) {
        return;
    }
    midiInLog.value.push(`unknown ${status} ${channel} ${message}`);
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
    midiOutLog.value = midiOutLog.value.slice(-25);
    midiInLog.value = midiInLog.value.slice(-25);
}

watch(outputChannels, (newChannels) => {
    player.setChannels(newChannels);
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
main {
    margin: 40px 100px;
}

.midi-section {
    margin-top: 20px;
    margin-bottom: 20px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: flex-start;
    gap: 20px;
}

.midi-section-row {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    gap: 10px;
}


/* Specific button styles */
.play-button {
    background-color: #37683c;
    color: #ffffff;
    padding: 8px 16px;
    cursor: pointer;
    border: none;
}

.play-button:hover:not(:disabled) {
    background-color: rgb(87, 146, 108);
}

.play-button:disabled {
    background-color: #2a3830;
    opacity: 0.7;
    cursor: not-allowed;
}

/* Table styles */
.image-table {
    margin-top: 20px;
    border-collapse: collapse;
    background-color: #1a1a1a;
}

.image-table td, .image-table th {
    padding: 10px;
    border: 1px solid #4e4e5a;
    max-width: 250px;
}


.image-table th {
    background-color: #2a2a2a;
}

.image-table td{

    position: relative;
}

.columns {
    display: flex;
    flex-direction: row;
    justify-content: stretch;
    gap: 40px;
}

.column {
    margin: 10px;
    min-width: 200px;
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
label {
    min-width: 150px;
}
.select-indicator {
    position: absolute;
    top: 0;
    left: -10px;
    width: 10px;
    bottom: 0;
    background-color: #41a84b;
    border-radius: 10px 0 0 10px;
    display: none;
}

.selected.select-indicator {
    display: block;
}

.playing-image {
    background-color: #41a84b;
}


</style>