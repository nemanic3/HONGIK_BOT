import { Suspense } from 'react';
import ReviewClient from './ReviewClient';

export default function ReviewPage() {
  return <Suspense fallback={<p>성적표를 불러오는 중입니다.</p>}><ReviewClient /></Suspense>;
}
