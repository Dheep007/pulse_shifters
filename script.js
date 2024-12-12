// Get elements
const canvas = document.getElementById("drawingCanvas");
const ctx = canvas.getContext("2d");
const colorPicker = document.getElementById("colorPicker");
const brushSize = document.getElementById("brushSize");
const clearCanvas = document.getElementById("clearCanvas");

// Set canvas size
canvas.width = window.innerWidth - 40;
canvas.height = window.innerHeight - 200; 

let isDrawing = false;
let lastX = 0;
let lastY = 0;
let minX = Infinity;
let minY = Infinity;
let maxX = -Infinity;
let maxY = -Infinity;

// Function to update the bounding box
function updateBoundingBox(x, y) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
}

// Event handlers
canvas.addEventListener("mousedown", (e) => {
    if (e.button === 2) return; // Ignore right-click for drawing
    isDrawing = true;
    [lastX, lastY] = [e.offsetX, e.offsetY];
    updateBoundingBox(lastX, lastY);
});

canvas.addEventListener("mousemove", (e) => {
    if (!isDrawing) return;
    ctx.strokeStyle = colorPicker.value;
    ctx.lineWidth = brushSize.value;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(e.offsetX, e.offsetY);
    ctx.stroke();

    [lastX, lastY] = [e.offsetX, e.offsetY];
    updateBoundingBox(lastX, lastY);
});

canvas.addEventListener("mouseup", () => (isDrawing = false));
canvas.addEventListener("mouseout", () => (isDrawing = false));

// Clear canvas and reset bounding box
clearCanvas.addEventListener("click", () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    minX = Infinity;
    minY = Infinity;
    maxX = -Infinity;
    maxY = -Infinity;
});


canvas.addEventListener("contextmenu", async (event) => {
    event.preventDefault(); // Prevent the default context menu

    if (minX === Infinity || minY === Infinity || maxX === -Infinity || maxY === -Infinity) {
        console.log("No bounding box detected");
        alert("No bounding box detected!");
        return;
    }

    // Add padding to the bounding box
    const padding = 10; // Adjust this value to avoid cutting off edges
    const paddedMinX = Math.max(0, minX - padding);
    const paddedMinY = Math.max(0, minY - padding);
    const paddedMaxX = Math.min(canvas.width, maxX + padding);
    const paddedMaxY = Math.min(canvas.height, maxY + padding);

    // Compute new dimensions
    const width = paddedMaxX - paddedMinX;
    const height = paddedMaxY - paddedMinY;

    // Create a temporary canvas for the cropped region
    const tempCanvas = document.createElement("canvas");
    const tempCtx = tempCanvas.getContext("2d");
    tempCanvas.width = width;
    tempCanvas.height = height;

    // Fill the temporary canvas with a white background
    tempCtx.fillStyle = "white";
    tempCtx.fillRect(0, 0, width, height);

    // Draw the bounding box region onto the temporary canvas
    tempCtx.drawImage(canvas, paddedMinX, paddedMinY, width, height, 0, 0, width, height);

    // Convert the cropped region to base64
    const croppedImage = tempCanvas.toDataURL();

    const data = {
        image: croppedImage,
        min_x: paddedMinX,
        min_y: paddedMinY,
        max_x: paddedMaxX,
        max_y: paddedMaxY,
    };

    try {
        // Send data to extract text
        const extractionResponse = await fetch("/image_extraction_js", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });

        const extractionResult = await extractionResponse.json();
        console.log("Extraction result:", extractionResult);

        if (extractionResult.extracted_text) {
            // Convert extracted text to speech
            const speechResponse = await fetch("/bbox_to_text", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: extractionResult.extracted_text }),
            });

            const speechResult = await speechResponse.json();
            console.log("Speech conversion result:", speechResult);

            // Save the extracted word and cropped image
            const saveWordResponse = await fetch("/save-word", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    word: extractionResult.extracted_text,
                    min_x: paddedMinX,
                    min_y: paddedMinY,
                    max_x: paddedMaxX,
                    max_y: paddedMaxY,
                    image: croppedImage,
                }),
            });

            const saveWordResult = await saveWordResponse.json();
            console.log("Save word result:", saveWordResult);

            if (saveWordResult.message) {
                alert(saveWordResult.message);
            } else {
                alert("Text extracted and converted to speech, but saving failed.");
            }
        } else {
            alert("No text found in the selected region.");
        }
    } catch (error) {
        console.error("Error processing the request:", error);
        alert("Failed to process the request. Check the console for details.");
    }
});



// Clear canvas and reset bounding box
clearCanvas.addEventListener("click", () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height); 
    minX = Infinity; 
    minY = Infinity;
    maxX = -Infinity;
    maxY = -Infinity;

    console.log("Canvas cleared and bounding box reset.");
});


document.getElementById("saveCanvas").addEventListener("click", () => {
    const canvas = document.getElementById("drawingCanvas");
    const context = canvas.getContext("2d");

    // Check if the canvas is empty
    const isCanvasEmpty = !context.getImageData(0, 0, canvas.width, canvas.height)
        .data.some(channel => channel !== 0); // Check if all pixel data is transparent

    if (isCanvasEmpty) {
        alert("The canvas is empty. Please draw something before saving.");
        return;
    }

    // Get image data as Base64 string
    const imageData = canvas.toDataURL("image/png");

    // Send the image data to the Python backend
    fetch("/save_canvas_image", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ image: imageData })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("Image saved successfully!");
            } else {
                alert("Failed to save the image.");
            }
        })
        .catch(error => {
            console.error("Error:", error);
            alert("An error occurred while saving the image.");
        });
});







// JavaScript to handle the click event
document.getElementById("mic-btn").addEventListener("click", function () {
    const extraButtons = document.getElementById("extra-buttons");
    extraButtons.classList.remove("hidden");
});


function startrecording() {
    fetch('/listen_thread', {
        method: 'GET', 
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById("show-area").innerText = data.message;
    })
    .catch(error => console.error('Error:', error));
}

function stoprecording() {
    fetch('/stop', {
        method: 'GET',
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById("show-area").innerText = data.message;
    })
    .catch(error => console.error('Error:', error));
}

function convertrecording() {
    document.getElementById("show-area").innerText = "Stopping and fetching text...";

    fetch('/display_text', {
        method: 'GET',
    })
    .then(response => response.json())
    .then(data => {
        console.log(data); 
       
        if (data.text) {
            document.getElementById("show-area").innerText = data.text;
        } else {
            document.getElementById("show-area").innerText = data.message;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById("show-area").innerText = "Error while fetching text.";
    });
}

function clearWritingSpace() {
    document.getElementById("show-area").innerText = "";
}


function backHidden() {
    document.getElementById('extra-buttons').classList.add('hidden')
}


function saverecording() {
    const textToSave = document.getElementById("show-area").innerText; 
    fetch('/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `text=${encodeURIComponent(textToSave)}`
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
    })
    .catch(error => console.error('Error:', error));
}





document.getElementById("convert").addEventListener("click", () => {
    fetch("/convert_text", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
    })
    .then(response => response.json())  // Parse the response as JSON
    .then(data => {
        const responseDiv = document.getElementById("response");
        
        // Check if the conversion was successful
        if (data.status === "success") {
            responseDiv.textContent = "Text converted successfully!";
            responseDiv.style.color = "green";  // Success message
        } else {
            responseDiv.textContent = `Error: ${data.message}`;
            responseDiv.style.color = "red";  // Error message
        }
    })
    .catch(error => {
        console.error("Error:", error);
        const responseDiv = document.getElementById("response");
        responseDiv.textContent = "An error occurred. Please try again.";
        responseDiv.style.color = "red";  // Error message
    });
});








document.getElementById("extract").addEventListener("click", () => {
    fetch("/extract_text", {
        method: "POST",
    })
    .then(response => response.json())
    .then(data => {
        const responseDiv = document.getElementById("response");
        
        if (data.status === "success") {
            responseDiv.textContent = `Text extracted successfully! Extracted Text: ${data.extracted_text}`;
            responseDiv.style.color = "green";
        } else {
            responseDiv.textContent = `Error: ${data.message}`;
            responseDiv.style.color = "red";
        }
    })
    .catch(error => {
        console.error("Error:", error);
        const responseDiv = document.getElementById("response");
        responseDiv.textContent = "An error occurred. Please try again.";
        responseDiv.style.color = "red";
    });
});


let currentInput = '';

function appendNumber(number) {
    currentInput += number;
    updateDisplay();
}

function appendOperator(operator) {
    currentInput += operator;
    updateDisplay();
}

function clearDisplay() {
    currentInput = '';
    updateDisplay();
}

function updateDisplay() {
    document.getElementById('display').value = currentInput;
}

function calculateResult() {
    try {
        currentInput = eval(currentInput);
        updateDisplay();
    } catch (error) {
        alert('Invalid expression');
        clearDisplay();
    }
}



let timeInSeconds = 3 * 60 * 60; // 3 hours in seconds
let timerInterval;

function formatTime(seconds) {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function updateTimer() {
    const timerDisplay = document.getElementById('timer');
    timerDisplay.textContent = formatTime(timeInSeconds);
}

function startTimer() {
    timerInterval = setInterval(() => {
        if (timeInSeconds > 0) {
            timeInSeconds--;
            updateTimer();
        } else {
            clearInterval(timerInterval);
        }
    }, 1000);
}

function reduceTime() {
    if (timeInSeconds > 3600) { // Ensure there's more than 1 hour to reduce
        timeInSeconds -= 3600; // Reduce by 1 hour
        updateTimer();
    } else {
        timeInSeconds = 0; // Prevent negative time
        updateTimer();
        clearInterval(timerInterval); // Stop the timer if time is zero
    }
}

document.getElementById('reduceTimeBtn').addEventListener('click', reduceTime);

// Initialize the timer display
updateTimer();
// Start the timer when the page loads
window.onload = startTimer;