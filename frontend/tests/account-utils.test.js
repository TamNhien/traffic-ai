import {test} from 'node:test'
import assert from 'node:assert/strict'
import {usernameProblem, readableApiDetail} from '../src/account-utils.js'

test('supports Vietnamese account name and normalization',()=>{
  assert.equal(usernameProblem('Đạt'),'')
  assert.equal(usernameProblem('Trần.Thị_Lý-2026'),'')
  assert.equal(usernameProblem('  Nhiền  '),'')
})

test('rejects invalid username in browser before mutation',()=>{
  for(const value of ['aa','Đạt 1','test@home','admin!','/admin','name-','🙃ok'])
    assert.notEqual(usernameProblem(value),'',value)
})

test('renders 422 validation detail as Vietnamese text, not object Object',()=>{
  const error=readableApiDetail([{loc:['body','username'],type:'value_error',msg:'Value error, Tên đăng nhập không hợp lệ'}],422)
  assert.match(error,/Tên đăng nhập/)
  assert.doesNotMatch(error,/\[object Object\]/)
})

test('handles flat error responses and authentication failures',()=>{
  assert.equal(readableApiDetail('Tên đăng nhập đã tồn tại',409),'Tên đăng nhập đã tồn tại')
  assert.match(readableApiDetail(null,401),/Phiên đăng nhập/)
  assert.equal(readableApiDetail({foo:'bar'},422),'Yêu cầu không hợp lệ. Vui lòng kiểm tra thông tin nhập.')
})
