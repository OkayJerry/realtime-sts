# Realtime Speech-to-Speech

![realtime-sts_diagram](https://github.com/user-attachments/assets/8013c4d3-76aa-4b11-a68d-1d139c4ba7e9)

## Quick Setup
1. ### Websocket Server
| Step | Terminal | Purpose | Quick Reference |
| - | - | - | - |
| 1 |   | Install dependencies. | `pip install -r requirements.txt` |
| 2 | 1 | Runs the server. | `python websocket-server/main.py` |
| 3 | 2 | Exposes server to Twilio. | `ngrok http 8081` |
| 4 |   | Runs the server. | `python websocket-server/main.py` |

2. ### Environment (.env) Variables
| Name | Purpose | How to Find |
| - | - | - |
| `OPENAI_API_KEY` |  For connecting to OpenAI's Realtime API.| [Sign In](https://platform.openai.com/api-keys) > `+ Create a new secret key` > `Create secret key` |
| `PUBLIC_URL` | To establish live, bidirectional communication stream. | On Terminal 2, `ngrok` will list this under "Session Status" as the forwarding URL. |
| `FIREBASE_SERVICE_ACCOUNT_KEY_PATH` | For storing call data (e.g. transcripts, events). | Create a [Google Firebase](https://console.firebase.google.com/) project and follow these [instructions](https://firebase.google.com/docs/admin/setup#initialize_the_sdk_in_non-google_environments). |

3. ### Twilio
| Step | Instruction |
| - | - |
| 1 | Create Twilio account. |
| 2 | Purchase and activate phone number. |
| 3 | Set "A call comes in" webhook to `https://forwarding-url-goes-here.ngrok.app/twiml`.

## Additional Plans
- [ ] Front end
- [ ] [Gemini Live](https://ai.google.dev/gemini-api/docs/live)
- [ ] Users
- [ ] Tool Calling
