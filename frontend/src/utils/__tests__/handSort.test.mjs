import test from 'node:test';
import assert from 'node:assert/strict';
import {
  NET_SORT_ORDERS,
  getNextNetSortOrder,
  getNetSortQueryParams,
  getNetSortTooltip,
} from '../handSort.js';

test('getNextNetSortOrder cycles correctly: none -> asc -> desc -> none', () => {
  // Initial: none (不排序) -> Click 1: asc (点一下正序)
  assert.equal(getNextNetSortOrder(NET_SORT_ORDERS.NONE), NET_SORT_ORDERS.ASC);
  assert.equal(getNextNetSortOrder('none'), 'asc');
  assert.equal(getNextNetSortOrder(), 'asc');

  // Click 2: asc -> desc (再点一下倒序)
  assert.equal(getNextNetSortOrder(NET_SORT_ORDERS.ASC), NET_SORT_ORDERS.DESC);
  assert.equal(getNextNetSortOrder('asc'), 'desc');

  // Click 3: desc -> none (再点一下不排序)
  assert.equal(getNextNetSortOrder(NET_SORT_ORDERS.DESC), NET_SORT_ORDERS.NONE);
  assert.equal(getNextNetSortOrder('desc'), 'none');

  // Full 4-step loop verification
  let current = 'none';
  current = getNextNetSortOrder(current);
  assert.equal(current, 'asc', '1st click must be ascending (正序)');
  current = getNextNetSortOrder(current);
  assert.equal(current, 'desc', '2nd click must be descending (倒序)');
  current = getNextNetSortOrder(current);
  assert.equal(current, 'none', '3rd click must be unsorted (不排序)');
  current = getNextNetSortOrder(current);
  assert.equal(current, 'asc', '4th click must cycle back to ascending (正序)');
});

test('getNetSortQueryParams maps sort states to backend query parameters', () => {
  // 'none' produces empty params (backend defaults to ended_at desc)
  assert.deepEqual(getNetSortQueryParams('none'), {});
  assert.deepEqual(getNetSortQueryParams(undefined), {});

  // 'asc' requests net_chips ascending
  assert.deepEqual(getNetSortQueryParams('asc'), {
    sort_by: 'net_chips',
    order: 'asc',
  });

  // 'desc' requests net_chips descending
  assert.deepEqual(getNetSortQueryParams('desc'), {
    sort_by: 'net_chips',
    order: 'desc',
  });
});

test('getNetSortTooltip returns proper prompt text for each state', () => {
  assert.equal(getNetSortTooltip('none'), '点击按净结果正序排列');
  assert.equal(getNetSortTooltip('asc'), '点击按净结果倒序排列');
  assert.equal(getNetSortTooltip('desc'), '点击恢复默认排序');
});
