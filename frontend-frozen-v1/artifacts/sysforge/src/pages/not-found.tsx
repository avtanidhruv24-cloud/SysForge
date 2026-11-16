import { ArrowLeft, Compass } from 'lucide-react';
import { Link } from 'wouter';

export default function NotFound() {
  return (
    <div className="sysforge-app" style={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', padding: 24 }}>
      <div className="panel" style={{ maxWidth: 470, width: '100%', padding: 28 }}>
        <div className="empty-icon"><Compass size={19} /></div>
        <div className="eyebrow">SYSFORGE / routing</div>
        <h1 className="page-title" style={{ fontSize: 32, marginTop: 10 }}>Surface not found</h1>
        <p className="page-description" style={{ marginBottom: 22 }}>This route is outside the laboratory map. Return to the source editor to continue the experiment.</p>
        <Link href="/" className="primary-button" data-testid="link-not-found-home"><ArrowLeft size={13} /> Return to source</Link>
      </div>
    </div>
  );
}