// Local image OCR only; no document parsing or student-data fixtures.
import Foundation
import Vision

func selectRecognitionLanguages(requested: [String], supported: [String]) throws -> [String] {
    let selected = requested.filter { supported.contains($0) }
    guard !selected.isEmpty else {
        throw NSError(domain: "AppleVisionOCR.NoSupportedLanguage", code: 2)
    }
    return selected
}

// OCR entry point
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
let requestedLanguages = ["ko-KR", "en-US"]
let supportedLanguages = try request.supportedRecognitionLanguages()
let selectedLanguages = try selectRecognitionLanguages(requested: requestedLanguages,
                                                       supported: supportedLanguages)
request.recognitionLanguages = selectedLanguages
request.usesLanguageCorrection = false
let handler = VNImageRequestHandler(url: URL(fileURLWithPath: CommandLine.arguments[1]))
try handler.perform([request])
let text = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    .joined(separator: "\n")
let unsupportedLanguages = requestedLanguages.filter { !supportedLanguages.contains($0) }
let warnings: [[String: String]] = unsupportedLanguages.isEmpty ? [] : [[
    "code": "unsupported_recognition_language",
    "message": "Unsupported requested languages: \(unsupportedLanguages.joined(separator: ", ")); " +
               "fallback uses \(selectedLanguages.joined(separator: ", "))."
]]
let result: [String: Any] = [
    "text": text, "provider": "apple_vision", "recognition_level": "accurate",
    "revision": request.revision, "requested_languages": requestedLanguages,
    "supported_languages": supportedLanguages, "recognition_languages": selectedLanguages,
    "unsupported_languages": unsupportedLanguages, "warnings": warnings
]
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: result))
