<template>
    <div>
        <h1>MFM</h1>
        
        <div class="midi-section">
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

        Upload image:
        <input type="file" @change="handleFileUpload" accept="image/*">
        
        <div class="columns">
            <div class="column">
                <table class="image-table">
                    <tr v-for="item in uploadedImages.values()" :key="item.id">
                        <td><img :src="item.imageUrl" width="200" /></td>
                <td>
                    <button 
                        @click="playImage(item)"
                        :disabled="!item.parameters"
                        class="play-button"
                    >
                        {{ item.parameters ? 'Play' : 'Analyzing...' }}
                    </button>
                </td>
                <td>
                    {{ item.dimensions.width }} x {{ item.dimensions.height }}
                </td>
                    </tr>
                </table>
            </div>
            <div class="column">
                <div v-for="(message, index) in midiLog" :key="index">
                    {{ message }}
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts"> 
import { ref, onMounted } from 'vue';
import { createMidiSender, MidiSender } from './util/MidiSender';
import { ImagePlayer } from './util/ImagePlayer';
import { Base64Binary } from './util/base64-binary';
interface ImageItem {
    id: number;
    imageUrl: string;
    dimensions: {width: number, height: number};
    parameters?: Map<string, Float32Array>;
    control_length: number;
}
interface AnalyzeResponse {
    control_length: number;
    parameters: {// base64 encoded float32 arrays
        intensity: number[];
        pitch: number[];
        density: number[];
        hue: number[];
        saturation: number[];
        value: number[];
        x_position: number[];
    }
}

const midiOutputs = ref<{id: string, name: string}[]>([]);
const selectedOutput = ref<string | null>(null);
const uploadedImages = ref<Map<number, ImageItem>>(new Map());
const midiLog = ref<string[]>([]);
const imagePlayers: ImagePlayer[] = [];

let midiSender: MidiSender | null = null;

const handleOutputChange = () => {
    if (midiSender && selectedOutput.value) {
        midiSender.setOutPort(selectedOutput.value);
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
            },
            control_length: 0
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
                const parametersMap = new Map<string, Float32Array>();
                for (const [key, value] of Object.entries(responseJson.parameters)) {
                    parametersMap.set(key, new Float32Array(value[0]));
                }
                uploadedImages.value.get(newItem.id).control_length = responseJson.control_length;
                uploadedImages.value.get(newItem.id).parameters = parametersMap;
            } catch (error) {
                console.error('Analysis failed:', error);
            }
        };
        reader.readAsDataURL(file);
    };
    img.src = imageUrl;
}

const playImage = (item: ImageItem) => {
    if (!item.parameters) return;
    // TODO: Implement playback using parameters
    if (imagePlayers.length === 0) {
        imagePlayers.push(new ImagePlayer());
    }
    imagePlayers[0].play(item.parameters, midiSender, item.control_length);
}

onMounted(async () => {
    midiSender = await createMidiSender();
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
    midiSender.noteOnCallback = handleNoteOn;
    midiSender.noteOffCallback = handleNoteOff;
    midiSender.controlChangeCallback = handleControlChange;
});

const handleNoteOn = (note: number, velocity: number) => {
    midiLog.value.push(`note on ${note} ${velocity}`);
    trimMidiLog();
}

const handleNoteOff = (note: number) => {
    midiLog.value.push(`note off ${note}`);
    trimMidiLog();
}

const handleControlChange = (control: number, value: number) => {
    midiLog.value.push(`control change ${control} ${value}`);
    trimMidiLog();
}

const trimMidiLog = () => {
    midiLog.value = midiLog.value.slice(-10);
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
</style>