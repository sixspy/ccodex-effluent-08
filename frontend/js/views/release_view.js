export const releaseViewTemplate = `
  <div class="grid-2">
    <div class="panel">
      <h3>准排放记录</h3>
      <table>
        <thead><tr><th>准排号</th><th>采样</th><th>口</th><th>值班</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="r in releases" :key="r.id">
            <td>{{ r.release_ref }}</td><td>{{ r.sample_code }}</td><td>{{ r.outfall_code }}</td>
            <td>{{ r.officer }}</td><td>{{ r.released_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>签发准排</h3>
      <label>候选采样（已裁定/已封批）</label>
      <select v-model.number="releaseForm.sample_id">
        <option v-for="s in releasableSamples" :key="s.id" :value="s.id">{{ s.sample_code }} · {{ s.status }} · {{ s.snapshot_ok ? "快照齐" : "缺快照" }}</option>
      </select>
      <label>值班员</label><input v-model="releaseForm.officer"/>
      <p v-if="releaseBlocked" class="warn">缺封批快照：无快照禁准，准排按钮已禁用</p>
      <div class="actions"><button :disabled="releaseBlocked" @click="createRelease">准排</button></div>
    </div>
  </div>`;
