© 2025 Luxembourg Institute of Science and Technology.
Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
 
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

## Attribution

The trust / costly-monitoring mechanism (`src/communication/trust.py`, the
trust phase in `src/game/game_round.py`, and the associated result metrics)
implements the design introduced by **FAIRGAME-Trust**, by Andrew Powell,
Nikita Huber, Dhanushka Dissanayake and Grace Ufeoshi — a fork of FAIRGAME
that made history disclosure a voluntary, costly decision (LOOK / NO_LOOK)
rather than an implicit assumption. The implementation here is independent
and follows FAIRGAME's own architecture and payoff conventions; the
mechanism, its configuration surface and its metrics are theirs.
