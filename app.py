# app.py
import multiprocessing as mp
import sys
import re
import traceback
from io import StringIO
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def runCode(code, conn, inputValue, individual):
    outputStream = StringIO()
    inputStream = StringIO(inputValue)
    sys.stdout = outputStream
    sys.stdin = inputStream
    if individual:
        __name__ = "__main__"
        description = "current run"
    else:
        description = "main run"
    try:
        exec(code)
    except SyntaxError as err:
        error_class = err.__class__.__name__
        detail = err.args[0]
        line_number = err.lineno
        outputString = "%s at line %d of %s: %s" % (error_class, line_number, description, detail)
        success = False
    except Exception as err:
        error_class = err.__class__.__name__
        detail = err.args[0]
        cl, exc, tb = sys.exc_info()
        line_number = traceback.extract_tb(tb)[-1][1]
        outputString = "%s at line %d of %s: %s" % (error_class, line_number, description, detail)
        success = False
    else: 
        outputString = outputStream.getvalue()
        success = True
        print("From child: outputStream = ", outputString)
    finally:
        sys.stdout = sys.__stdout__
        sys.stdin = sys.__stdin__
        conn.send([success, outputString])
        conn.close()

def runCodeHandler(code, inputValue, individual):
    stringStream = StringIO()
    parentConn, childConn = mp.Pipe()
    p = mp.Process(target=runCode, args=(code, childConn, inputValue, individual))
    p.start()
    p.join(3)
    if(p.exitcode == None):
        # Timeout occured
        p.terminate()
        return False, "Timeout occured"
    else:
        success, printedResult = parentConn.recv()
        return success, printedResult

@app.route('/run-individual/', methods=['GET'])
def runIndividual():
    # Retrieve the name from url parameter
    json = request.get_json()
    code = json.get("code", None)
    inputValue = json.get("input", "")

    # For debugging
    print(f"got code {code}")
    print(f"got input {inputValue}")

    response = {}

    # Check if user sent a code at all
    if not code:
        response["ERROR"] = "no code found, please send code."
    # Now the user entered a valid code
    else:
        success, outputValue = runCodeHandler(code, inputValue, True)
        if success:
            response["RESULT"] = outputValue
        else:
            response["ERROR"] = outputValue

    # Return the response in json format
    return jsonify(response)

@app.route('/run-main/', methods=['POST'])
def runMain():
    json = request.get_json()
    codes = json.get("codes", None)
    inputValue = json.get("input", "")
    response = {}
    if not codes:
        response["ERROR"] = "no code found, please send code."
        return jsonify(response)
    mainCode = codes[0]
    firstLine, _newline, restOfMain = mainCode.partition("\n")
    candidateCodes = codes[1:]
    validPattern = r"^\s*import\s*(?:participant(\d+)\s*,\s*)*participant(\d+)\s*$"
    valid = re.match(validPattern,firstLine)
    if not valid:
        response["ERROR"] = "no initial import found on line 1 or malformed, please include initial input on line 1."
        return jsonify(response)
    pattern = r"participant(\d+)"
    matches = re.findall(pattern,firstLine)
    matches = [int(match) for match in matches]
    if len(matches) <= len(candidateCodes) and min(matches) > 0 and max(matches) <= len(candidateCodes):
        # Compile codes together
        totalCode = ""
        for match in matches:
            totalCode += candidateCodes[match-1]
        totalCode += restOfMain
        # Run the code
        success, outputValue = runCodeHandler(totalCode, inputValue, False)
        if success:
            response["RESULT"] = outputValue
        else:
            response["ERROR"] = outputValue
    else:
        response["ERROR"] = "import found on line 1, but it is malformed."
    return jsonify(response)

# A welcome message to test our server
@app.route('/')
def index():
    return "<h1>Welcome to our server !!</h1>"

if __name__ == '__main__':
    # Threaded option to enable multiple instances for multiple user access support
    mp.set_start_method('spawn')
    app.run(threaded=True, port=5000)