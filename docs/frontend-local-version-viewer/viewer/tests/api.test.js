import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  API_BASE,
  fetchProjectStatus,
  fetchLatestReport,
  fetchSnapshots,
  postUpdate,
  fetchJobStatus,
  fetchL1Graph,
  fetchDiff,
  fetchL2Graph,
  fetchStructure,
  fetchLayerExplanation,
  fetchNotes,
  postNote,
  fetchDiffExplanation,
  fetchStaticUpdateViewModel,
  fetchStaticL1ViewModel,
} from '../js/api.js';

function mockFetch(data, ok = true) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok,
    json: async () => data,
  });
}

describe('api.js', () => {
  let fetchSpy;

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('API_BASE', () => {
    it('is exported as empty string (same-origin)', () => {
      expect(API_BASE).toBe('');
    });
  });

  describe('fetchProjectStatus', () => {
    it('calls /api/project with cache no-store', async () => {
      fetchSpy = mockFetch({ status: 'ok' });
      await fetchProjectStatus();
      expect(fetchSpy).toHaveBeenCalledWith('/api/project', { cache: 'no-store' });
    });

    it('returns json data', async () => {
      const data = { project_path: '/foo' };
      mockFetch(data);
      const result = await fetchProjectStatus();
      expect(result).toEqual(data);
    });
  });

  describe('fetchLatestReport', () => {
    it('calls /api/report/latest with cache no-store', async () => {
      fetchSpy = mockFetch({});
      await fetchLatestReport();
      expect(fetchSpy).toHaveBeenCalledWith('/api/report/latest', { cache: 'no-store' });
    });

    it('returns json data', async () => {
      const data = { l0_summary: 'summary' };
      mockFetch(data);
      const result = await fetchLatestReport();
      expect(result).toEqual(data);
    });
  });

  describe('fetchSnapshots', () => {
    it('calls /api/snapshots with cache no-store', async () => {
      fetchSpy = mockFetch({ snapshots: [] });
      await fetchSnapshots();
      expect(fetchSpy).toHaveBeenCalledWith('/api/snapshots', { cache: 'no-store' });
    });

    it('returns json data', async () => {
      const data = { snapshots: [{ version_id: 'v1' }] };
      mockFetch(data);
      const result = await fetchSnapshots();
      expect(result).toEqual(data);
    });
  });

  describe('fetchL1Graph', () => {
    it('uses /api/l1 with no query string when versionId is null', async () => {
      fetchSpy = mockFetch({});
      await fetchL1Graph(null);
      expect(fetchSpy).toHaveBeenCalledWith('/api/l1', { cache: 'no-store' });
    });

    it('uses /api/l1 with no query string when versionId is omitted', async () => {
      fetchSpy = mockFetch({});
      await fetchL1Graph();
      expect(fetchSpy).toHaveBeenCalledWith('/api/l1', { cache: 'no-store' });
    });

    it('encodes versionId as query string', async () => {
      fetchSpy = mockFetch({});
      await fetchL1Graph('abc def');
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/l1?version_id=abc%20def',
        { cache: 'no-store' }
      );
    });

    it('returns json data', async () => {
      const data = { nodes: [], edges: [] };
      mockFetch(data);
      const result = await fetchL1Graph(null);
      expect(result).toEqual(data);
    });
  });

  describe('fetchDiff', () => {
    it('encodes both baseline and current in query string', async () => {
      fetchSpy = mockFetch({});
      await fetchDiff('v1', 'v2');
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/diff?baseline=v1&current=v2',
        { cache: 'no-store' }
      );
    });

    it('returns json data', async () => {
      const data = { node_states: {} };
      mockFetch(data);
      const result = await fetchDiff('v1', 'v2');
      expect(result).toEqual(data);
    });
  });

  describe('fetchL2Graph', () => {
    it('calls /api/l2/<encoded featureId>', async () => {
      fetchSpy = mockFetch({});
      await fetchL2Graph('feat-x');
      expect(fetchSpy).toHaveBeenCalledWith('/api/l2/feat-x', { cache: 'no-store' });
    });

    it('encodes featureId in URL', async () => {
      fetchSpy = mockFetch({});
      await fetchL2Graph('feat x');
      expect(fetchSpy).toHaveBeenCalledWith('/api/l2/feat%20x', { cache: 'no-store' });
    });

    it('returns json data', async () => {
      const data = { nodes: [], edges: [] };
      mockFetch(data);
      const result = await fetchL2Graph('feat-x');
      expect(result).toEqual(data);
    });
  });

  describe('postUpdate', () => {
    it('sends POST to /api/update with JSON body containing three fields', async () => {
      fetchSpy = mockFetch({ job_id: '123' });
      await postUpdate('/old', '/new', 'zh-Hant');
      expect(fetchSpy).toHaveBeenCalledWith('/api/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_path: '/old', new_path: '/new', output_language: 'zh-Hant' }),
      });
    });

    it('returns json data', async () => {
      const data = { job_id: 'abc' };
      mockFetch(data);
      const result = await postUpdate('/old', '/new', 'zh-Hant');
      expect(result).toEqual(data);
    });
  });

  describe('fetchJobStatus', () => {
    it('calls /api/update/status/<jobId>', async () => {
      fetchSpy = mockFetch({ status: 'running' });
      await fetchJobStatus('job-1');
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/update/status/job-1',
        { cache: 'no-store' }
      );
    });

    it('returns json data', async () => {
      const data = { status: 'completed' };
      mockFetch(data);
      const result = await fetchJobStatus('job-1');
      expect(result).toEqual(data);
    });
  });

  describe('fetchStructure', () => {
    it('calls /api/structure with cache no-store', async () => {
      fetchSpy = mockFetch({ nodes: [] });
      await fetchStructure();
      expect(fetchSpy).toHaveBeenCalledWith('/api/structure', { cache: 'no-store' });
    });

    it('returns json data', async () => {
      const data = { nodes: [{ node_id: 'n1' }] };
      mockFetch(data);
      const result = await fetchStructure();
      expect(result).toEqual(data);
    });
  });

  describe('fetchLayerExplanation', () => {
    it('calls /api/layer-explanation/<featureId>/<layer>', async () => {
      fetchSpy = mockFetch({ explanation: 'text' });
      await fetchLayerExplanation('feat-1', 'l2');
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/layer-explanation/feat-1/l2',
        { cache: 'no-store' }
      );
    });

    it('returns json data', async () => {
      const data = { explanation: 'hello' };
      mockFetch(data);
      const result = await fetchLayerExplanation('feat-1', 'l2');
      expect(result).toEqual(data);
    });
  });

  // postGenerateL2 / postGenerateLayerExplanation tests removed in T5-V (丙案 D1):
  // those generation endpoints were retired; only GET read functions remain.

  describe('fetchNotes', () => {
    it('calls /api/notes with URLSearchParams query string', async () => {
      fetchSpy = mockFetch({ notes: [] });
      const params = new URLSearchParams({ mode: 'diff', feature_id: 'feat-1' });
      await fetchNotes(params);
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/notes?' + params.toString(),
        { cache: 'no-store' }
      );
    });

    it('accepts plain object as params', async () => {
      fetchSpy = mockFetch({ notes: [] });
      await fetchNotes({ mode: 'diff', feature_id: 'feat-1' });
      const call = fetchSpy.mock.calls[0][0];
      expect(call).toContain('/api/notes?');
      expect(call).toContain('feature_id=feat-1');
    });

    it('returns json data', async () => {
      const data = { notes: [{ display_name: 'Alice' }] };
      mockFetch(data);
      const result = await fetchNotes(new URLSearchParams());
      expect(result).toEqual(data);
    });
  });

  describe('postNote', () => {
    it('sends POST to /api/notes with JSON body', async () => {
      fetchSpy = mockFetch({ note: {} });
      const payload = { mode: 'diff', feature_id: 'feat-1', name_input: 'Alice', comment: 'hi' };
      await postNote(payload);
      expect(fetchSpy).toHaveBeenCalledWith('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    });

    it('returns json data', async () => {
      const data = { note: { display_name: 'Alice' } };
      mockFetch(data);
      const result = await postNote({});
      expect(result).toEqual(data);
    });
  });

  describe('fetchDiffExplanation', () => {
    it('calls /api/diff-explanations/<featureId> with params', async () => {
      fetchSpy = mockFetch({ explanation: null });
      const params = new URLSearchParams({ baseline_version_id: 'v1', current_version_id: 'v2' });
      await fetchDiffExplanation('feat-1', params);
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/diff-explanations/feat-1?' + params.toString(),
        { cache: 'no-store' }
      );
    });

    it('accepts plain object as params', async () => {
      fetchSpy = mockFetch({ explanation: null });
      await fetchDiffExplanation('feat-1', { baseline_version_id: 'v1' });
      const call = fetchSpy.mock.calls[0][0];
      expect(call).toContain('/api/diff-explanations/feat-1?');
      expect(call).toContain('baseline_version_id=v1');
    });

    it('returns json data', async () => {
      const data = { explanation: { impact_summary: 'changed' } };
      mockFetch(data);
      const result = await fetchDiffExplanation('feat-1', new URLSearchParams());
      expect(result).toEqual(data);
    });
  });

  // postGenerateDiffExplanation tests removed in T5-V (丙案 D1): generation retired,
  // only fetchDiffExplanation (GET read) remains.

  describe('fetchStaticUpdateViewModel', () => {
    it('calls ./data/update-view-model.json with cache no-store', async () => {
      fetchSpy = mockFetch({ mode: 'update-report' });
      await fetchStaticUpdateViewModel();
      expect(fetchSpy).toHaveBeenCalledWith('./data/update-view-model.json', { cache: 'no-store' });
    });

    it('returns json data', async () => {
      const data = { mode: 'update-report', diff_available: true };
      mockFetch(data);
      const result = await fetchStaticUpdateViewModel();
      expect(result).toEqual(data);
    });
  });

  describe('fetchStaticL1ViewModel', () => {
    it('calls ./data/l1-view-model.json with cache no-store', async () => {
      fetchSpy = mockFetch({ nodes: [] });
      await fetchStaticL1ViewModel();
      expect(fetchSpy).toHaveBeenCalledWith('./data/l1-view-model.json', { cache: 'no-store' });
    });

    it('returns json data', async () => {
      const data = { nodes: [{ id: 'feat-1' }] };
      mockFetch(data);
      const result = await fetchStaticL1ViewModel();
      expect(result).toEqual(data);
    });
  });
});
