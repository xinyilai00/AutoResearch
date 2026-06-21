export default function StageCard({ name, status = "pending" }) {
  return (
    <section className="stage-card">
      <h2>{name}</h2>
      <p>{status}</p>
    </section>
  );
}
