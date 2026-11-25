export const sealViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>封批快照</h3>
      <table>
        <thead><tr><th>封批号</th><th>采样</th><th>代</th><th>快照</th><th>最新</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="s in seals" :key="s.id">
            <td>{{ s.seal_ref }}</td><td>{{ s.sample_code }}</td><td>{{ s.sample_generation }}</td>
            <td>{{ s.snapshot }}</td>
            <td :class="s.is_latest ? 'pass' : 'muted'">{{ s.is_latest ? "最新" : "旧代" }}</td>
            <td>{{ s.sealed_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>执行封批</h3>
      <label>可封批采样</label>
      <select v-model.number="sealForm.sample_id">
        <option v-for="s in sealableSamples" :key="s.id" :value="s.id">{{ s.sample_code }} · {{ s.status }}</option>
      </select>
      <label>快照（可空自动）</label><input v-model="sealForm.snapshot"/>
      <div class="actions"><button class="warn" @click="createSeal">封批升代</button></div>
    </div>
    <div class="panel">
      <h3>缺最新快照批次（无快照禁准）</h3>
      <table>
        <thead><tr><th>采样</th><th>状态</th><th>当前代</th><th>快照代</th></tr></thead>
        <tbody>
          <tr v-for="s in snapshotMissingSamples" :key="s.id">
            <td>{{ s.sample_code }}</td><td>{{ s.status }}</td>
            <td>{{ s.generation }}</td>
            <td class="warn">{{ s.latest_snapshot_generation ?? "—" }}</td>
          </tr>
          <tr v-if="!snapshotMissingSamples.length"><td colspan="4" class="pass">全部在管批次快照齐套</td></tr>
        </tbody>
      </table>
    </div>
  </div>`;
